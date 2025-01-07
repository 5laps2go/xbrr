import importlib.util
import os
import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from urllib.parse import urljoin
from logging import getLogger

from bs4 import BeautifulSoup

if importlib.util.find_spec("pandas") is not None:
    import pandas as pd

from xbrr.base.reader.base_reader import BaseReader
from xbrr.base.reader.xbrl_doc import XbrlDoc
from xbrr.xbrl.reader.element_schema import ElementSchema
from xbrr.xbrl.reader.element_value import ElementValue
from xbrr.xbrl.reader.role_schema import RoleSchema
from xbrr.xbrl.reader.schema_tree import SchemaTree
from xbrr.xbrl.reader.taxonomy_repository import TaxonomyRepository


class Reader(BaseReader):

    def __init__(self, xbrl_doc: XbrlDoc, taxonomy_repo=None, save_dir: str = ""):
        super().__init__("edinet")
        self.xbrl_doc = xbrl_doc
        self.taxonomy_repo = taxonomy_repo if taxonomy_repo is not None\
            else TaxonomyRepository(save_dir)
        self.save_dir = save_dir

        self.schema_tree = None
        self._role_dic = {}
        self._context_dic = {}
        self._value_dic = {}
        self._namespace_dic = {}
        self.schema_dic = None

        self.logger = getLogger(__name__)
        self.debug_print = []
    
        self.setup_initial_environment(save_dir)

    def __reduce_ex__(self, proto):
        return type(self), (self.xbrl_doc, self.taxonomy_repo, )

    def setup_initial_environment(self, save_dir:str):
        self._context_dic, self._value_dic, self._namespace_dic =\
            ElementValue.read_xbrl_values(self, self.xbrl_doc.xbrl)

        self.schema_dic = self.taxonomy_repo.load_schema_files(self._namespace_dic)
        self.schema_tree = SchemaTree(self, self.xbrl_doc.find_path('xsd'))
    
    @property
    def custom_roles(self):
        if len(self._role_dic) == 0:
            linkbase = self.xbrl_doc.default_linkbase
            xml = self.read_uri(self.schema_tree.find_kind_uri(linkbase['doc']))
            link_node, roleRef = self.get_linkbase_tag(xml, linkbase['link_node'], linkbase['roleRef'])
            self._role_dic.update(RoleSchema.read_role_ref(self, xml, link_node, roleRef))
        return self._role_dic

    @property
    def namespaces(self):
        return self._namespace_dic

    def get_schema_by_link(self, link:str) -> ElementSchema:
        assert "#" in link                  # http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2020-11-01/jppfs_rt_2020-11-01.xsd#rol_ConsolidatedLabel
        ns_or_xsduri = link.split("#")[0]   # http://...(edinet|tdnet).../...
        element = link.split("#")[-1]       # tse-acedjpfr-36450_PromotionReturnIncomeNOI
        xsd_dic = self.schema_dic.get_dict(ns_or_xsduri, element)

        elemschema = xsd_dic.get(element, None)
        if elemschema is None:
            xsduri = self.find_xsduri(ns_or_xsduri) if not ns_or_xsduri.endswith('.xsd') else ns_or_xsduri
            xsd_dic.update(ElementSchema.read_schema(self, xsduri))
            elemschema = xsd_dic.get(element, ElementSchema(name=element, reference=link)) # avoid reference error
        return elemschema

    def get_role(self, role_name) -> RoleSchema:
        if '/' in role_name:
            role_name = role_name.rsplit('/', 1)[-1]
        return self.custom_roles[role_name]

    def find_xsduri(self, namespace:str) -> str:
        """find xsd uri by namespace """
        assert namespace.startswith("http:"), "no namespace found:{}".format(namespace)
        try:
            return self.schema_tree.find_xsduri(namespace)
        except LookupError:
            return self.taxonomy_repo.find_xsduri(namespace)

    def read_uri(self, uri:str) -> BeautifulSoup:
        "read xsd or xml specifed by uri"
        assert uri.endswith('.xsd') or uri.endswith('.xml') or uri.startswith('http:'), "no xsduri found:{}".format(uri)
        if not uri.startswith('http'):
            uri = os.path.join(self.xbrl_doc.dirname, uri)
        return self.taxonomy_repo.read_uri(uri)
    
    def get_linkbase_tag(self, doc:BeautifulSoup, *args):
        ns_prefixes = {v: k for k,v in doc._namespaces.items()}
        if (link_prefix:=ns_prefixes.get("http://www.xbrl.org/2003/linkbase")) is not None:
            return ("{}:{}".format(link_prefix, arg) for arg in args)
        return args
    
    def get_label_uri(self, xsduri:str) -> str:
        "get the uri of the label for the xsd uri"
        laburi = self.schema_tree.find_kind_uri('lab', xsduri)
        return laburi

    def read_schema_by_role(self, role_name, preserve_pre:Dict, preserve_cal:Dict, fix_cal_node:List):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes = {}
        linkbase = self.xbrl_doc.default_linkbase
        self.logger.debug("-------------- Section presentation -----------------")
        for docuri in self.schema_tree.linkbaseRef_iterator(linkbase['doc']):
            self.make_node_tree(nodes, role_name, docuri, linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'], preserve_pre)

        if list(self.schema_tree.linkbaseRef_iterator('cal')) != []:
            self.logger.debug("-------------- Section calculation ------------------")
            for docuri in self.schema_tree.linkbaseRef_iterator('cal'):
                self.make_node_tree(nodes, role_name, docuri, "calculationLink", "calculationArc", "summation-item", preserve_cal)
            self.patch_calc_node_tree(nodes, fix_cal_node)
        return self.flatten_to_schemas(nodes)
    
    def patch_calc_node_tree(self, nodes, fix_cal_node):
        self.fix_calc_link_for_parent_subtotal(nodes)
        self.eliminate_non_value_calc_leaf(nodes)
        self.fix_missing_calc_link(nodes, fix_cal_node)
        self.eliminate_extra_subtotal(nodes)

    def make_node_tree(self, nodes, role_name, docuri, link_node, arc_node, arc_role, preserve_dict):
        def t(name):
            return name.split('_')[-1]
        def get_name(loc):
            return loc["xlink:href"].split("#")[-1]
        def get_absxsduri(docuri, xsduri):
            if xsduri.startswith('http'): return xsduri
            return urljoin(docuri, xsduri)

        doc = self.read_uri(docuri)
        link_node, arc_node = self.get_linkbase_tag(doc, link_node, arc_node)
        assert len(doc.contents)==0 or "xlink" in doc._namespaces
        
        locs = {}
        # for loc in doc.select(f"linkbase > {link_node} > loc"): # "link:loc"
        for loc in doc.find_all("loc"):
            locs[loc["xlink:label"]] = loc

        # for role in doc.select(f"linkbase > {link_node}[role=\"{self.get_role(role_name).uri}\"]"): # doc.find_all(linknode, {"xlink:role": self.get_role(role_name).uri}):
        for role in doc.find_all(link_node, {"xlink:role": self.get_role(role_name).uri}):
            for i, arc in enumerate(role.find_all(arc_node, recursive=False)):
                assert arc["xlink:arcrole"].split('/')[-1] in ['parent-child','summation-item','domain-member', 'dimension-domain', 'all', 'hypercube-dimension']
                if not arc["xlink:arcrole"].endswith(arc_role):
                    continue

                arctype = arc_node.split(':')[-1]
                parent = locs[arc["xlink:from"]]
                child = locs[arc["xlink:to"]]

                if get_name(child) not in nodes:
                    xsduri = get_absxsduri(docuri, child["xlink:href"])
                    c = ElementSchema.create_from_reference(self, xsduri)
                    nodes[get_name(child)] = Node(c)

                if get_name(parent) not in nodes:
                    xsduri = get_absxsduri(docuri, parent["xlink:href"])
                    p = ElementSchema.create_from_reference(self, xsduri)
                    nodes[get_name(parent)] = Node(p)

                # preserve presentation/calculation struct
                if t(get_name(child)) in preserve_dict:
                    if t(get_name(parent)) in preserve_dict[t(get_name(child))]:
                        if arctype=='presentationArc':
                            self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                            nodes[get_name(child)].preserve_parent(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'))
                        if arctype=='calculationArc':
                            self.logger.debug("{}:{} --> {}:w{} p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("weight",0),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                            nodes[get_name(child)].preserve_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                    else:
                        self.logger.debug("{} -> {}: o{} p{} {}".format(get_name(parent), get_name(child), arc.get('order','0'), arc.get('priority','0'),arc.get('use','')))
                        if arctype=='calculationArc' and \
                            (nodes[get_name(parent)].no_derive() or any([t(x.name) in preserve_dict[t(get_name(child))] for x in nodes[get_name(parent)].get_derive_chain()])):
                            nodes[get_name(child)].preserve_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                    continue

                if arctype == "calculationArc":
                    self.logger.debug("{}:{} --> {}:w{} p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("weight",0),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                else:
                    self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_parent(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'))

    def fix_missing_calc_link(self, nodes, fix_cal_node):
        def prior_order(orphan:Node, missing:Node):
            return orphan.presentation_order < missing.presentation_order
        def missing_derived_orphans(fnode:Node):
            leafs = [k for (k,v) in nodes.items() if v!=fnode and k in self._value_dic and v.no_derive()]
            missings = [x for x in leafs if prior_order(nodes[x], fnode)]
            return sorted(missings, reverse=True, key=lambda x: nodes[x].presentation_order)
        def nearest_missing(fnode:Node):
            for nearer in [v for v in nodes.values() if v.has_derive(fnode) and v.is_leaf and v.derived_count > 0]:
                if missing_derived_orphans(nearer):
                    nearest = nearest_missing(nearer)
                    return nearer if nearest is None else nearest
            return None
        def validate_calc(fnode:Node):
            return validate_value(fnode, fnode, 0)
        def validate_value(fnode:Node, onode:Node, w:int):
            def epsvalue(node1:Node, node2:Node):
                if (result := cvalue(node1))==0: result = cvalue(node2)
                return (1000 if result%10*6 else 10**6 if result%10**9 else 10**9) * 2
            def cvalue(node:Node):
                ev = next(filter(lambda x: not x.context_ref['id'].startswith('Prior'), self._value_dic.get(node.name,[])), None)
                return float(ev.value) if ev is not None and ev.value!='NaN' else 0
            result = cvalue(fnode)
            epsilon = epsvalue(fnode, onode)
            value = sum([float(v.get_weight(fnode)) * cvalue(v) for v in nodes.values() if v.has_derive(fnode)])
            onode_delta = value + w*cvalue(onode) - result
            if result == 0 and abs(value - w*cvalue(onode)) < epsilon:  # replace nonstandard item to standard item (OperatingLoss to OperatingIncome)
                if fnode.name not in self._value_dic:
                    self._value_dic[fnode.name] = self._value_dic[onode.name]
                return True
            return abs(value - result) > epsilon and onode_delta < epsilon if w!=0 else abs(value - result) < epsilon
        for name in fix_cal_node:
            missing = next(filter(lambda x: x.split('_')[-1]==name, nodes), None)
            if missing is None or len(nodes[missing].parents)==0:
                continue
            for orphan in missing_derived_orphans(nodes[missing]):
                if (nearest:=nearest_missing(nodes[missing])) is not None and prior_order(nodes[orphan], nearest):
                    w = 1
                    if any([x in nearest.name for x in ['Expense','Cost','SGA']]): w = -w
                    if any([x in orphan for x in ['Expense','Cost','SGA']]): w = -w
                    if validate_value(nearest, nodes[orphan], w):
                        if validate_calc(nodes[missing]):
                            # print('######{} {} nearest {} <== {}'.format(validate_calc(nodes[missing]), nearest.name, missing, orphan))
                            nodes[orphan].add_derive(nearest, '', '0', '1', str(w))
                        continue
                w = 1
                if any([x in missing for x in ['Expense','Cost']]): w = -w
                if any([x in orphan for x in ['Expense','Cost']]): w = -w
                if validate_value(nodes[missing], nodes[orphan], w):
                    nodes[orphan].add_derive(nodes[missing], '', '0', '1', str(w))

    def fix_calc_link_for_parent_subtotal(self, nodes):
        parent_subtotal = {}
        context = None
        for name in nodes:
            n = nodes[name]
            if name in self._value_dic and n.parent_name in self._value_dic:
                children = parent_subtotal.get(n.parent_name, [])
                parent_subtotal[n.parent_name] = children + [n]
                if not context:
                    contexts = [x.context_ref['id'] for x in self._value_dic[name] if not x.context_ref['id'].startswith('Prior')]
                    if contexts:
                        context = contexts[0]

        for parent_name,children in parent_subtotal.items():
            # children make subtotal
            if nodes[parent_name].validate_subtotal(children, context, self._value_dic):
                for child in [x for x in children if x.no_derive()]:
                    child.add_derive(nodes[parent_name], '', '0', '1', str(1))
                continue
            # derive children can not make subtotal (内訳であるためSUBTOTALと一致しない)
            derived = [x for x in children if not x.no_derive()]
            if not nodes[parent_name].validate_subtotal(derived, context, self._value_dic):
                for child in derived:
                    child.remove_derive(nodes[parent_name])

    def eliminate_non_value_calc_leaf(self, nodes):
        def no_current_value(name):
            return all([x.context.startswith('Prior') or x.value=='NaN' for x in self._value_dic[name]])
        def current_nan(name):
            return all([x.value=='NaN' for x in self._value_dic[name] if not x.context.startswith('Prior')])
        # nodes preserves child, parent order (derived, derives order)
        for name in nodes:
            n = nodes[name]
            while n is not None and n.derived_count==0 and len(n.derives)> 0 \
                 and (n.name not in self._value_dic or no_current_value(n.name)):
                derive = n.get_derive()
                n.remove_derive_all()
                n = derive
    
    def eliminate_extra_subtotal(self, nodes):
        def epsvalue(node:Node):
            result = cvalue(node)
            return (1000 if result%10*6 else 10**6 if result%10**9 else 10**9) * 2
        def cvalue(node:Node):
            ev = next(filter(lambda x: not x.context_ref['id'].startswith('Prior'), self._value_dic.get(node.name,[])), None)
            return float(ev.value) if ev is not None and ev.value!='NaN' else 0
        def calc_error(node:Node):
            result = cvalue(node)
            values = [(k,float(v.get_weight(node)) * cvalue(v)) for k,v in nodes.items() if v.has_derive(node)]
            return (sum([v for k,v in values]) - result, values)

        for oinode in [v for k,v in nodes.items() if k.endswith('OperatingIncome')]:
            epsilon = epsvalue(oinode)
            diff, values = calc_error(oinode)
            if abs(diff) > epsilon:
                self.logger.info("# extra item found in OperatingIncome")
                for k,v in values:
                    # if abs(v-diff) < epsilon and nodes[k].no_derived():
                    if abs(v-diff) < epsilon:
                        self.logger.info("# extra item is {}".format(k))
                        found = False
                        # for k2,v2 in [(k2,v2) for k2,v2 in values if k2!=k]:
                        #     diff2, values2 = calc_error(nodes[k2])
                        #     if values2 and abs(diff + diff2) < epsilon:
                        #         nodes[k].push_derive(nodes[k2])
                        #         found = True
                        #         break
                        if not found:
                            nodes[k].remove_derive(oinode)

    def flatten_to_schemas(self, nodes):
        schemas = []
        Node.init_derive_path()

        parent_depth = -1
        for name in nodes:
            if parent_depth < nodes[name].depth:
                parent_depth = nodes[name].depth

        for name0 in nodes:
            n = nodes[name0]
            if n.element.abstract=='true':
                continue
            item = {}
            parents = n.get_parents()
            if n.is_leaf:
                parents = parents + ([""] * (parent_depth - len(parents)))
                empty_order = float(n.order)
            else:
                parents = parents + [n] + ([""] * (parent_depth - len(parents) - 1))
                empty_order = 99.0

            for i, p in zip(reversed(range(parent_depth)), parents):
                name = p.name if not isinstance(p, str) else p
                label = p.label if not isinstance(p, str) else p
                order = float(p.order) if not isinstance(p, str) else empty_order
                item[f"parent_{i}"] = name
                item[f"parent_{i}_label"] = label
                item[f"parent_{i}_order"] = order

            item["order"] = empty_order
            item["depth"] = n.get_derive_path()

            item.update(n.element.to_dict())
            schemas.append(item)

        schemas = pd.DataFrame(schemas)
        schemas.sort_values(by=[c for c in schemas.columns
                                if c.endswith("order")],
                            inplace=True)

        return schemas


    def read_value_by_role(self, role_link:str, preserve_pre:Dict = {}, preserve_cal:Dict = {}, fix_cal_node:List = [], scope:str = ""):
        """Read XBRL values in a dataframe which are specified by role and/or context.

        Arguments:
            role_link {str} -- role name or role uri
        Keyword Arguments:
            scope {str} -- context name prefix, eg "Current" for "Current*" (default: {""} for everything)
            preserve_pre: presentation structure to avoid xbrl data errors
            preserve_cal: calculation structure to avoid xbrl data errors
            fix_cal_node: nodes to fix missing calculation link
        Returns:
            xbrl_df -- Saved XbRL dataframe.
        """
        def calc_value(row, dict):
            def filter(x, base):
                return x['depth'].endswith(base) and x['depth'][0] in ['+','-']
            results = []
            if row['depth'][0] in ['+','-']:
                return results
            inputs = [x for x in dict if filter(x, row['depth'])]
            contexts = [(x['context'],x['member']) for x in inputs]
            for context in sorted(set(contexts), key=contexts.index):
                item = row.to_dict()
                value = 0
                input_src = [x for x in inputs if x['context']==context[0] and x['member']==context[1]]
                if len(input_src) < 2: continue
                for input in input_src:
                    for k,v in [(k,v) for k,v in input.items() if k not in item]:
                        item[k] = v
                    add = int(input['value']) if input['value']!='NaN' else 0
                    value += add if input['depth'][0] == '+' else -add
                item['value'] = str(value)
                results.append(item)
            return results

        schemas = self.read_schema_by_role(role_link, preserve_pre, preserve_cal, fix_cal_node)
        if len(schemas) == 0:
            return None

        xbrl_data = []
        for i, row in schemas.iterrows():
            tag_name = row['name']
            row['name'] = ':'.join(tag_name.rsplit('_', 1))
            if tag_name not in self._value_dic:
                xbrl_data += calc_value(row, xbrl_data)
                continue

            results = []
            for value in sorted(self._value_dic[tag_name], reverse=True, key=lambda x: x.context_ref['id']):
                if not value.context.startswith(scope):
                    continue
                item = row.to_dict()
                for k, v in value.to_dict().items():
                    if k not in ['name','label']:
                        item[k] = v
                results.append(item)
            
            if len(results) > 0:
                xbrl_data += results

        xbrl_df = pd.DataFrame(xbrl_data)
        if self.debug_print:
            # pd.set_option('display.width', 1000)
            self.logger.info('\n'.join(list(set(self.debug_print))))
            # self.logger.info(xbrl_data[['name','value','depth', 'consolidated','label']])
            self.debug_print = []
        return xbrl_df

    def find_value_names(self, candidates:List[str]) -> List[str]:
        values = []
        for name in candidates:
            values += [x for x in self._value_dic.keys() if name in x]
        return values
    
    def find_value_name(self, findop) -> str:
        return next(filter(findop, self._value_dic.keys()), None)

    def findv(self, tag):
        id = tag.replace(':', '_')
        return self._value_dic.get(id, [None])[0] # find returns the first element value only.


class Node():

    def __init__(self, element, order=0):
        self.element = element
        self.prohibited = None # (parent, order, priority)
        self.parents = []       # e: {'parent':Node, 'order': str, 'priority': str}
        self.children_count = 0
        self.derives = []       # e: {'target':Node, 'use':str, 'order':str, 'priority':str, 'weight':str}
        self.derived_count = 0

    @property
    def parent_name(self):
        if not self.parents:
            return None
        return self.parents[0]['parent'].name

    @property
    def order(self):
        if not self.parents:
            return 0
        if len(self.parents) > 1:
            self.debug_print = 'more than two parents found at {}: {}'.format(self.name, [x['parent'].name for x in self.parents])
        return self.parents[0]['order']
    
    def add_parent(self, parent, use:str, priority:str, order:str ):
        if use=='prohibited':
            self.prohibited = {'parent':parent, 'order':order, 'priority':priority}
            for x in [x for x in self.parents if parent==x['parent'] and priority>x['priority'] and float(order)==float(x['order'])]:
                self.parents.remove(x)
                x['parent'].children_count -= 1
            return
        if self.prohibited is not None:
            if parent == self.prohibited['parent'] and float(order) == float(self.prohibited['order'])\
                and priority < self.prohibited['priority']:
                return

        self.parents.append({'parent':parent, 'priority':priority, 'order':order})
        parent.children_count += 1

    def preserve_parent(self, parent, use:str, priority:str, order:str ):
        if use=='prohibited':
            self.prohibited = {'parent':parent, 'order':order, 'priority':priority}
        else:
            self.parents.append({'parent':parent, 'priority':priority, 'order':order})
            parent.children_count += 1

        if self.prohibited is not None and len(self.parents) > 1:
            for x in [x for x in self.parents if self.prohibited['parent']==x['parent']
                      and self.prohibited['priority']>x['priority'] and float(self.prohibited['order'])==float(x['order'])]:
                self.parents.remove(x)
                x['parent'].children_count -= 1

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
    def is_leaf(self):
        return self.children_count == 0
    
    @property
    def depth(self):
        return len(self.get_parents())

    @property
    def presentation_order(self):
        parents = [float(x.order) for x in self.get_parents()]
        parents.append(float(self.order))
        parents.append(99.)     # short leaf has lower order of the longer leaf. (see flatten_to_schemas)
        return tuple(parents)

    def get_parents(self):
        parents = []
        if len(self.parents) == 0:
            return parents
        else:
            ps = [x['parent'] for x in self.parents]
            while len(ps) != 0 and ps[0] not in parents:
                parents.insert(0, ps[0])
                ps = [x['parent'] for x in ps[0].parents]
            return parents

    def add_derive(self, target, use:str, priority:str, order:str, weight:str):
        target_derives = [x for x in self.derives if x['target']==target and float(x['order'])==float(order)]
        for x in target_derives:
            if priority > x['priority']:
                self.derives.remove(x)
                if use!='prohibited':
                    self.derives.append({'target':target, 'use':use, 'priority':priority, 'order':order, 'weight':weight})
                target.update_derive_count(+1 if use!='prohibited' else -1)
        if len(target_derives)==0:
            self.derives.append({'target':target, 'use':use, 'priority':priority, 'order':order, 'weight':weight})
            if use!='prohibited': target.update_derive_count(+1)
    
    def preserve_derive(self, target, use:str, priority:str, order:str, weight:str):
        self.derives.append({'target':target, 'use':use, 'priority':priority, 'order':order, 'weight':weight})
        target.update_derive_count(+1 if use!='prohibited' else 0)
        if len(self.derives) > 2:
            prohibited_derives = [x for x in self.derives if x['use']=='prohibited']
            for p in prohibited_derives:
                target_derives = [x for x in self.derives if x['target']==p['target'] and x['use']!='prohibited']
                for x in target_derives:
                    if float(p['order'])==float(x['order']) and p['priority']>x['priority']:
                        self.derives.remove(p)
                        self.derives.remove(x)
                        p['target'].update_derive_count(-1)

                if target_derives and \
                    any([float(x['order'])==float(p['order']) and x['priority']>=p['priority'] for x in target_derives]):
                    self.derives.remove(p)
    
    def remove_derive_all(self):
        for x in [x for x in self.derives if x['use']!='prohibited']:
            x['target'].update_derive_count(-1)
        self.derives = []
    
    def remove_derive(self, target):
        derives = [x for x in self.derives if x['target']!=target]
        if len(derives)!=len(self.derives):
            target.update_derive_count(-1)
            self.derives = derives
    
    def push_derive(self, new_target):
        for x in [x for x in self.derives if x['use']!='prohibited']:
            x['target'].update_derive_count(-1)
            if float(self.get_weight(x['target'])) == -1 and float(new_target.get_weight(x['target'])) == -1:
                x['weight'] = x['weight'].replace('-','')
            x['target'] = new_target
            x['target'].update_derive_count(1)

    def get_derive(self):
        derives =  [x for x in self.derives if x['use']!='prohibited']
        return derives[0]['target'] if derives else None

    def update_derive_count(self, diff:int):
        self.derived_count += diff

    def get_derive_chain(self):
        return self._get_derive_chain([])
    def _get_derive_chain(self, path0):
        path = path0 + [self]
        active_chains = [[x['target'], *x['target']._get_derive_chain(path)] for x
            in self.derives if x.get('use','')!='prohibited' and x['target'] not in path]
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        if len(sorted_chains) > 1: print("!!! get_derive_chain:",sorted_chains)
        return sorted_chains[0] if len(sorted_chains) > 0 else []

    def has_derive(self, target):
        derives = [x['target'] for x in self.derives if x['use']!='prohibited']
        if target in derives:
            return True
        return False

    def get_weight(self, target):
        derives = [x['weight'] for x in self.derives if x['use']!='prohibited' and x['target']==target]
        return derives[0] if len(derives)>0 else None

    def no_derived(self):
        return self.derived_count == 0
    
    def no_derive(self):
        return not any([x['use']!='prohibited' for x in self.derives])
    
    def validate_subtotal(self, children, context, value_dic):
        def epsvalue(v1, v2, count):
            result = v1 if v1!=0 else v2
            return (1000 if result%10*6 else 10**6 if result%10**9 else 10**9) * count
        def cvalue(node:Node, context):
            ev = next(filter(lambda x: x.context_ref['id']==context, value_dic.get(node.name,[])), None)
            return float(ev.value) if ev is not None and ev.value!='NaN' else 0
        result = cvalue(self, context)
        value = sum([cvalue(v, context) for v in children])
        return abs(value - result) < epsvalue(result, value, len(children))

    children_list = {}
    base_node = None
    def get_child_index(self, child):
        children = Node.children_list.get(self, [])
        if child not in children:
            children.append(child)
            Node.children_list[self] = children
        child_index = children.index(child)
        return '123456789abcdefghijklmnopqrstuvwxyz'[child_index] if child_index < 35 else '0'

    def get_derive_subpath(self):
        return self._get_derive_subpath([])
    def _get_derive_subpath(self, path0):
        path = path0 + [self]
        if len(self.derives)==0 and self.element.data_type in ['monetary','perShare']:
            return [(Node.base_node.get_child_index(self),'1')]
        active_chains = [[(x['target'].get_child_index(self),x['weight']), *x['target']._get_derive_subpath(path)] for x
            in self.derives if x.get('use','')!='prohibited' and x['target'] not in path]
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        return sorted_chains[0] if len(sorted_chains) > 0 else [(Node.base_node.get_child_index(self),'1')]

    @classmethod
    def init_derive_path(cls):
        Node.children_list = {}
        Node.base_node = Node(None)

    def get_derive_path(self):
        path = self.get_derive_subpath()
        sign = sum([x[1].startswith('-') for x in path])
        sign_str = ('-' if sign%2==1 else '*') if sign>0 else '+'
        path_str = ''.join([x[0] for x in path])
        return sign_str + path_str if self.derived_count==0 else path_str
