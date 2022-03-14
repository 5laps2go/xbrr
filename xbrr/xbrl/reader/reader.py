import os
import importlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from bs4 import BeautifulSoup
if importlib.util.find_spec("pandas") is not None:
    import pandas as pd
from xbrr.base.reader.base_reader import BaseReader
from xbrr.edinet.reader.doc import Doc
from xbrr.xbrl.reader.element_schema import ElementSchema
from xbrr.xbrl.reader.role_schema import RoleSchema
from xbrr.xbrl.reader.element_value import ElementValue

class Reader(BaseReader):

    def __init__(self, xbrl_doc: Doc, taxonomy=None, save_dir: str = ""):
        super().__init__("edinet")
        self.xbrl_doc = xbrl_doc
        self.save_dir = save_dir
        self._xsd_dic = {}
        self._role_dic = {}
        self._context_dic, self._value_dic, self._namespace_dic =\
            ElementValue.read_xbrl_values(self, self.xbrl)

        root = Path(self.save_dir).joinpath("external")
        self.taxonomies_root = root
        self.taxonomies = self.xbrl_doc.create_taxonomies(root)

    def __reduce_ex__(self, proto):
        return type(self), (self.xbrl_doc, self.taxonomy)

    @property
    def custom_roles(self):
        if len(self._role_dic) == 0:
            linkbase = self.xbrl_doc.default_linkbase
            self._role_dic.update(RoleSchema.read_role_ref(self, linkbase['doc'], linkbase['link_node']))
        return self._role_dic

    @property
    def taxonomy_year(self):
        return list(map(
            lambda x: x.taxonomy_year(*self.xbrl_doc.published_date),
            self.taxonomies.values()))

    @property
    def namespaces(self):
        return self._namespace_dic

    @property
    def xbrl(self):
        return self.xbrl_doc.xbrl

    def get_schema_by_link(self, link:str) -> ElementSchema:
        assert "#" in link
        xsduri = link.split("#")[0]
        element = link.split("#")[-1]
        if element not in self._xsd_dic:
            self._xsd_dic.update(ElementSchema.read_schema(self, xsduri))
            # prepare label xml href dict from local xsd
            ElementSchema.read_label_taxonomy(self, xsduri, self._xsd_dic)
        return self._xsd_dic[element]

    def get_role(self, role_name) -> RoleSchema:
        if '/' in role_name:
            role_name = role_name.rsplit('/', 1)[-1]
        return self.custom_roles[role_name]

    def read_uri(self, uri:str) -> BeautifulSoup:
        "read xsd or xml specifed by uri"
        def fullyear_report_date(published_date:datetime, kind:str):
            if kind != 'a':
                duration = self.findv('jpdei_cor_TypeOfCurrentPeriodDEI')
                if duration is not None:
                    q = int(duration.value[1]) if duration.value[1].isdigit() else 2 # second quater
                    return published_date - timedelta(days=q*90), kind
            return published_date, kind
        taxonomy_prefixies = [x for x in self.taxonomies if uri.startswith(x)]
        if len(taxonomy_prefixies) > 0:
            taxonomy_prefix = taxonomy_prefixies[0]
            self.taxonomies[taxonomy_prefix].download(
                *fullyear_report_date(*self.xbrl_doc.published_date))

        path = self._uri_to_path(uri)
        with open(path, encoding="utf-8-sig") as f:
            xml = BeautifulSoup(f, "lxml-xml")
        return xml

    def read_label_of_xsd(self, xsduri:str) -> BeautifulSoup:
        "read label linkbase content specified by xsd uri"
        laburi = self.xbrl_doc.find_laburi(xsduri, 'lab')
        return self.read_uri(laburi)

    def _uri_to_path(self, uri:str) -> str:
        taxonomy_prefixies = [x for x in self.taxonomies if uri.startswith(x)]
        if self.taxonomies and len(taxonomy_prefixies) > 0:
            taxonomy_prefix = taxonomy_prefixies[0]
            path = os.path.join(self.taxonomies[taxonomy_prefix].path, uri.replace(taxonomy_prefix, ""))
        else: # for local uri
            path = self.xbrl_doc.find_path(uri)
        return path

    def read_schema_by_role(self, role_name, use_cal_link=False):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes = {}
        linkbase = self.xbrl_doc.default_linkbase
        self.make_node_tree(nodes, role_name, linkbase['doc'], linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'])
        if use_cal_link:
            self.make_node_tree(nodes, role_name, self.xbrl_doc.cal, "link:calculationLink", "link:calculationArc", "summation-item")
        return self.flatten_to_schemas(nodes)

    def make_node_tree(self, nodes, role_name, doc, link_node, arc_node, arc_role):
        role = doc.find(link_node, {"xlink:role": self.get_role(role_name).uri})
        if role is None:
            return []

        def get_name(loc):
            return loc["xlink:href"].split("#")[-1]

        locs = {}
        for loc in role.find_all("loc"): # "link:loc"
            locs[loc["xlink:label"]] = loc

        for i, arc in enumerate(role.find_all(arc_node)):
            if not arc["xlink:arcrole"].endswith(arc_role):
                continue

            parent = locs[arc["xlink:from"]]
            child = locs[arc["xlink:to"]]

            if get_name(child) not in nodes:
                c = ElementSchema.create_from_reference(self, child["xlink:href"])
                nodes[get_name(child)] = Node(c, arc["order"])
            else:
                nodes[get_name(child)].order = arc["order"]

            if get_name(parent) not in nodes:
                p = ElementSchema.create_from_reference(self, parent["xlink:href"])
                nodes[get_name(parent)] = Node(p, i)

            nodes[get_name(child)].add_parent(nodes[get_name(parent)])

    def flatten_to_schemas(self, nodes):
        schemas = []

        parent_depth = -1
        for name in nodes:
            if parent_depth < nodes[name].depth:
                parent_depth = nodes[name].depth

        for name in nodes:
            n = nodes[name]
            item = {}
            parents = n.get_parents()
            parents = parents + ([""] * (parent_depth - len(parents)))

            for i, p in zip(reversed(range(parent_depth)), parents):
                name = p if isinstance(p, str) else p.name
                label = p if isinstance(p, str) else p.label
                # print order: p1(c1, c2) => c1(=p1.order), c2(=p1.order), p1(=p1order+0.1)
                order = float(n.order)+0.1 if isinstance(p, str) else float(p.order)
                item[f"parent_{i}"] = name
                item[f"parent_{i}_label"] = label
                item[f"parent_{i}_order"] = order

            item["order"] = float(n.order)
            item["depth"] = n.depth
            item.update(n.element.to_dict())
            schemas.append(item)

        schemas = pd.DataFrame(schemas)
        schemas.sort_values(by=[c for c in schemas.columns
                                if c.endswith("order")],
                            inplace=True)

        return schemas


    def read_value_by_role(self, role_link:str, scope:str = "", use_cal_link:bool = False):
        """Read XBRL values in a dataframe which are specified by role and/or context.

        Arguments:
            role_link {str} -- role name or role uri
        Keyword Arguments:
            scope {str} -- context name prefix, eg "Current" for "Current*" (default: {""} for everything)
            use_cal_link: calculation link used after presentation link (default: {False})
        Returns:
            xbrl_data -- Saved XbRL values.
        """
        schemas = self.read_schema_by_role(role_link)
        if len(schemas) == 0:
            return None

        xbrl_data = []
        for i, row in schemas.iterrows():
            tag_name = row['name']
            if tag_name not in self._value_dic:
                continue

            results = []
            for value in self._value_dic[tag_name]:
                if not value.context.startswith(scope):
                    continue
                item = row.to_dict()
                for k, v in value.to_dict().items():
                    if not k.endswith('label'):
                        item[k] = v
                item['name'] = ':'.join(tag_name.rsplit('_', 1))

                results.append(item)
            
            if len(results) > 0:
                xbrl_data += results

        xbrl_data = pd.DataFrame(xbrl_data)
        return xbrl_data

    def find_value_names(self, candidates:List[str]) -> List[str]:
        values = []
        for name in candidates:
            values += [x for x in self._value_dic.keys() if name in x]
        return values

    def findv(self, tag):
        id = tag.replace(':', '_')
        if id not in self._value_dic:
            return None
        return self._value_dic[id][0] # find returns the first element value only.


class Node():

    def __init__(self, element, order=0):
        self.element = element
        self.parent = None
        self.order = order

    def add_parent(self, parent):
        self.parent = parent

    @property
    def name(self):
        return self.element.name

    @property
    def label(self):
        return self.element.label

    @property
    def reference(self):
        return self.element.reference

    @property
    def depth(self):
        return len(self.get_parents())

    @property
    def path(self):
        parents = list(reversed(self.get_parents()))
        if len(parents) == 0:
            return self.name
        else:
            path = str(self.order) + " " + self.name
            for p in parents:
                path = p.name + "/" + path
            return path

    def get_parents(self):
        parents = []
        if self.parent is None:
            return parents
        else:
            p = self.parent
            while p is not None:
                parents.insert(0, p)
                p = p.parent
            return parents
