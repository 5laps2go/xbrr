import os
import importlib
from datetime import datetime
from pathlib import Path
from typing import Dict
from bs4 import BeautifulSoup
if importlib.util.find_spec("pandas") is not None:
    import pandas as pd
from xbrr.base.reader.base_reader import BaseReader
from xbrr.edinet.reader.doc import Doc
from xbrr.edinet.reader.taxonomy import Taxonomy
from xbrr.edinet.reader.element import Element
from xbrr.edinet.reader.element_schema import ElementSchema
from xbrr.edinet.reader.role_schema import RoleSchema
from xbrr.edinet.reader.element_value import ElementValue

class Reader(BaseReader):

    def __init__(self, xbrl_doc: Doc, taxonomy=None, save_dir: str = ""):
        super().__init__("edinet")
        self.xbrl_doc = xbrl_doc
        self.save_dir = save_dir
        self._linkbaseRef = {}
        self._xsd_dics: Dict[str, ElementSchema] = {}
        self._role_dic = {}
        self._context_dic = {}
        self._cache = {}
        self._context_dic, self._value_dic, self._namespace_dic =\
            ElementValue.read_xbrl_values(self, self.xbrl.find("xbrli:xbrl"))

        if isinstance(taxonomy, Taxonomy):
            self.taxonomy = taxonomy
        else:
            root = Path(self.save_dir).joinpath("external")
            self.taxonomy = Taxonomy(root)
        self.taxonomy_year = ""
        self.__set_taxonomy_year()



    def set_cache(self, cache):
        self._cache = cache
        return self

    def __reduce_ex__(self, proto):
        return type(self), (self.xbrl_doc, self.taxonomy)

    def __set_taxonomy_year(self): # TODO: TDNET specific method required. this is EDINET specific method.
        self.taxonomy_year = ""
        date = self.findv("jpdei_cor:CurrentFiscalYearEndDateDEI").value
        kind = self.findv("jpdei_cor:TypeOfCurrentPeriodDEI").value
        date = datetime.strptime(date, "%Y-%m-%d")
        for y in sorted(list(self.taxonomy.TAXONOMIES.keys()), reverse=True):
            boarder_date = datetime(int(y[:4]), 3, 31)
            if kind[0] in ("Q", "H") and date > boarder_date:
                self.taxonomy_year = y
            elif date >= boarder_date:
                if y == 2019:
                    self.taxonomy_year = "2019_cg_ifrs"
                else:
                    self.taxonomy_year = y

            if self.taxonomy_year:
                break

    @property
    def roles(self):
        role_refs = self.find_all("link:roleRef")
        roles = {}
        for e in role_refs:
            element = e.element
            link = element["xlink:href"]
            roles[element["roleURI"]] = {
                "link": element["xlink:href"],
                "name": self.read_role_by_link(link).label
            }

        return roles

    @property
    def taxonomy_path(self):
        return self.taxonomy.root.joinpath("taxonomy", str(self.taxonomy_year))

    @property
    def namespaces(self):
        return self._namespace_dic

    @property
    def xbrl(self):
        path = self.xbrl_doc.find_path('xbrl')
        return self._read_from_cache(path)

    def _read_from_cache(self, path):
        if path not in self._cache:
            with open(path, encoding="utf-8-sig") as f:
                xml = BeautifulSoup(f, "lxml-xml")
            self._cache[path] = xml
        return self._cache[path]

    def read_by_link(self, link):
        assert "#" in link
        xsduri = link.split("#")[0]
        element = link.split("#")[-1]
        xsd_dic = self.get_xsd_dic(xsduri)
        return xsd_dic[element]

    def get_xsd_dic(self, xsduri):
        if xsduri in self._xsd_dics:
            xsd_dic = self._xsd_dics[xsduri]
        else:
            xsd_dic = ElementSchema.read_schema(self, xsduri)
            # prepare label xml href dict from local xsd
            ElementSchema.read_label_taxonomy(self, xsduri, xsd_dic)
            #label_path = self._find_file(_dir, extention)
            self._xsd_dics[xsduri] = xsd_dic
        return xsd_dic

    def read_role_by_link(self, link):
        assert "#" in link
        role_xsd = link.split("#")[0]
        element = link.split("#")[-1]
        if element in self._role_dic:
            return self._role_dic[element]
        
        RoleSchema.read_schema(self, role_xsd, self._role_dic)
        assert element in self._role_dic
        return self._role_dic[element]


    def read_by_xsduri(self, xsduri, kind):
        if xsduri.startswith(self.taxonomy.prefix):
            self.taxonomy.download(self.taxonomy_year)

        path = self._xsduri_to_path(xsduri, kind)
        with open(path, encoding="utf-8-sig") as f:
            xml = BeautifulSoup(f, "lxml-xml")
        return xml

    def _xsduri_to_path(self, xsduri, kind):
        href = self.xbrl_doc.find_xmluri(kind, xsduri=xsduri)
        if self.taxonomy and href.startswith(self.taxonomy.prefix):
            path = os.path.join(self.taxonomy_path, href.replace(self.taxonomy.prefix, ""))
        else:
            # for local uri
            path = self.xbrl_doc.find_path(href)
        return path

    def has_role_in_link(self, role_link, link_type):
        if link_type == "presentation":
            doc = self.xbrl_doc.pre
        elif link_type == "calculation":
            doc = self.xbrl_doc.cal
        else:
            return False

        role = doc.find("link:roleRef", {"roleURI": role_link})
        if role is not None:
            return True
        else:
            return False

    def read_schema_by_role(self, role_link, link_type="presentation",
                            label_kind="", label_verbose=False):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        doc = None
        link_node = ""
        arc_node = ""
        if link_type == "presentation":
            doc = self.xbrl_doc.pre
            link_node = "link:presentationLink"
            arc_node = "link:presentationArc"
        elif link_type == "calculation":
            doc = self.xbrl_doc.cal
            link_node = "link:calculationLink"
            arc_node = "link:calculationArc"
        else:
            raise Exception(f"Does not support {link_type}.")

        schemas = []
        role = doc.find(link_node, {"xlink:role": role_link})
        if role is None:
            return schemas

        def get_name(loc):
            return loc["xlink:href"].split("#")[-1]

        nodes = {}
        arc_role = ""
        if link_type == "calculation":
            arc_role = "summation-item"
        else:
            arc_role = "parent-child"

        locs = {}
        for loc in role.find_all("link:loc"):
            locs[loc["xlink:label"]] = loc

        for i, arc in enumerate(role.find_all(arc_node)):
            if not arc["xlink:arcrole"].endswith(arc_role):
                print("Unexpected arctype.")
                continue

            parent = locs[arc["xlink:from"]]
            child = locs[arc["xlink:to"]]

            if get_name(child) not in nodes:
                # c = create(self, child["xlink:href"]).set_alias(child["xlink:label"])
                c = ElementSchema.create_from_reference(self, child["xlink:href"])
                nodes[get_name(child)] = Node(c, arc["order"])
            else:
                nodes[get_name(child)].order = arc["order"]

            if get_name(parent) not in nodes:
                # p = create(self, parent["xlink:href"]).set_alias(parent["xlink:label"])
                p = ElementSchema.create_from_reference(self, parent["xlink:href"])
                nodes[get_name(parent)] = Node(p, i)

            nodes[get_name(child)].add_parent(nodes[get_name(parent)])

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
                order = "0" if isinstance(p, str) else p.order
                item[f"parent_{i}"] = name
                item[f"parent_{i}_label"] = ""
                item[f"parent_{i}_order"] = order

            item["order"] = n.order
            item["depth"] = n.depth
            item.update(n.element.to_dict())
            schemas.append(item)

        schemas = pd.DataFrame(schemas)
        schemas.sort_values(by=[c for c in schemas.columns
                                if c.endswith("order")],
                            inplace=True)

        label_dict = pd.Series(schemas["label"].tolist(),
                               index=schemas["name"].tolist()).to_dict()

        for i, row in schemas.iterrows():
            for j in range(parent_depth):
                name = row[f"parent_{j}"]
                if name in label_dict:
                    schemas.loc[i, f"parent_{j}_label"] = label_dict[name]

        return schemas

    def read_value_by_role(self, role_link, link_type="presentation",
                           label_kind="", label_verbose=False):

        schemas = self.read_schema_by_role(role_link, link_type,
                                           label_kind, label_verbose)
        if len(schemas) == 0:
            return None

        xbrl_data = []
        for i, row in schemas.iterrows():
            tag_name = row['name']
            if tag_name not in self._value_dic:
                continue

            results = []
            for value in self._value_dic[tag_name]:
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

    def findv(self, tag):
        id = tag.replace(':', '_')
        if id not in self._value_dic:
            return None
        return self._value_dic[id][0] # find returns the first element value only.

    def find_all(self, tag, attrs={}, recursive=True, text=None,
                 limit=None, **kwargs):
        elements = self.xbrl.find_all(
                        tag, attrs, recursive, text, limit, **kwargs)

        return [self._to_element(tag, e) for e in elements]

    def _to_element(self, tag, element):
        if element is None:
            return None

        reference = tag.replace(":", "_")

        if element.namespace:
            try:
                xsdloc = self.xbrl_doc.find_xsduri(element.namespace)
                reference = f"{xsdloc}#{reference}"
            except LookupError:
                reference = f"{element.namespace}/unknown.xsd#{reference}"
            return Element(tag, element, reference, self)


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
