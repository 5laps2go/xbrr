import importlib.util
import os
import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set
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
            self.make_node_tree(nodes, role_name, docuri, linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'])

        if list(self.schema_tree.linkbaseRef_iterator('cal')) != []:
            self.logger.debug("-------------- Section calculation ------------------")
            preserve_parents = set(sum(preserve_cal.values(),[]))
            for docuri in self.schema_tree.linkbaseRef_iterator('cal'):
                self.make_node_tree(nodes, role_name, docuri, "calculationLink", "calculationArc", "summation-item")
            self.patch_calc_node_tree(nodes, preserve_pre, preserve_cal, fix_cal_node)
        return self.flatten_to_schemas(nodes)
    
    def patch_calc_node_tree(self, nodes, preserve_pre:Dict, preserve_cal:Dict, fix_cal_node):
        def select_context(vlist, context):
            list = [x for x in vlist if x.context_ref.get('id','')==context and x.value!='NaN' and x.unit!=''] # isTextBlock: x.unit!=''
            return list[0] if list else None
        counter = {}
        for name in [n for n in nodes if n in self._value_dic and self._value_dic[n][0].data_type=='monetary']:
            for context in [x.context_ref['id'] for x in self._value_dic.get(name,[])]:
                if not context.startswith('Prior'):
                    count = counter.get(context,0)
                    counter[context] = count + 1
        context = max(counter, key=counter.get)
        context_value_dic = {k:select_context(v,context) for k,v in self._value_dic.items() if select_context(v,context)}

        self.fix_not_preserve_link('pre', nodes, preserve_pre, set([]))
        preserve_parents = set(sum(preserve_cal.values(),[]))
        self.fix_not_preserve_link('cal', nodes, preserve_cal, preserve_parents)
        
        self.fix_calc_link_for_parent_subtotal(nodes, context_value_dic)
        self.eliminate_non_value_calc_leaf(nodes)
        self.fix_missing_calc_link(nodes, fix_cal_node, context_value_dic)
        self.fix_extra_calc_link(nodes, fix_cal_node, context_value_dic)

    def make_node_tree(self, nodes, role_name, docuri, link_node, arc_node, arc_role):
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

                if arctype == "calculationArc":
                    self.logger.debug("{}:{} --> {}:w{} p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("weight",0),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                else:
                    self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_parent(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'))

    def fix_not_preserve_link(self, type, nodes, preserve_dict, preserve_parents):
        def t(name):
            return name.split('_')[-1]
        for name in nodes:
            if t(name) in preserve_dict:
                nparents = []
                if type=='pre': nparents = nodes[name].get_ascendants()
                if type=='cal':
                    nparent = nodes[name].get_derive()
                    nparents = [nparent] if nparent is not None else []
                for nparent in nparents:
                    parent = nparent.name
                    if t(parent) not in preserve_dict[t(name)]:
                        if type=='cal' and t(parent) in preserve_parents and not nodes[parent].no_derive() and not any([t(x.name) in preserve_dict[t(name)] for x in nodes[parent].get_derive_chain()]):
                            self.logger.debug("{} X-> {}".format(parent,name))
                            nodes[name].remove_derive(nparent)
                        if type=='pre':
                            self.logger.debug("{} X-> {}".format(parent,name))
                            nodes[name].remove_parent(nparent)
            else:
                if type=='cal':
                    nodes[name].omit_deleted_derives()

    def fix_missing_calc_link(self, nodes, fix_cal_node, context_vdic):
        def t(name):
            return name.split('_')[-1]
        def make_missing_link(derived, orphans):
            if derived is None or not orphans:
                return
            derived_value, diff, epsilon = derived.cvalue(context_vdic, nodes.values())
            if abs(diff) < epsilon:
                return
            orphan_values = [x.cvalue(context_vdic, nodes.values())[0] for x in orphans]
            for pat in [(1, 0), (-1, 0), (1, 1), (-1, 1), (-1, 0, 1), (-1, 0, 0, 1)]:
                pat2 = [x for x in pat][0:len(orphans)]
                vs = [pat2[i]*orphan_values[i] for i in range(len(pat2))]
                if abs(sum(vs)+diff) < epsilon or abs(sum(vs)-derived_value) < epsilon:
                    removed = []
                    if abs(sum(vs)-derived_value) < epsilon:
                        removed = derived.remove_derive_children(nodes.values())
                    for i in range(len(pat2)):
                        if pat2[i]!=0:
                            self.logger.debug("!{} --> {}:w{}".format(derived.name, orphans[i].name,pat[i]))
                            orphans[i].add_derive(derived, '', '0', '1', str(pat2[i]))
                            if len([x for x in pat2[i:] if x==0])>0 or removed:
                                orphans_sub = removed+[orphans[i] for i in range(i,len(pat2)) if pat2[i]==0] if i+1!=len(pat2) \
                                    else orphans[i+1:] if len(orphans)>len(pat2) else []
                                make_missing_link(orphans[i], orphans_sub)
                    break

        cal_nodes = [v for k,v in nodes.items() if t(k) in fix_cal_node]
        pre_base = set([x for v in cal_nodes for x in v.get_parent()])
        candidates = [v for k,v in nodes.items() if v in cal_nodes or v.leading_figures_wo_derive(pre_base, context_vdic)]
        derived,orphans = None,[]
        for missing in sorted(candidates, reverse=True, key=lambda x: x.presentation_order):
            if t(missing.name) in fix_cal_node:
                orphans.append(missing)
                make_missing_link(derived, orphans)
                derived = missing
                orphans = []
                continue
            orphans.append(missing)
        make_missing_link(derived, orphans)
    
    def fix_extra_calc_link(self, nodes, fix_cal_node, context_vdic):
        def t(name):
            return name.split('_')[-1]
        def eliminate_extra_link(node):
            derives = sorted([v for v in nodes.values() if v.has_derive(node)], reverse=True, key=lambda x: x.presentation_order)
            node_value, diff, epsilon = node.cvalue(context_vdic, derives)
            if abs(diff) < epsilon:
                return
            # found extra derives
            derives_values = [float(v.get_weight(node)) * float(context_vdic[v.name].value) for v in derives]
            for pat in [(1,0),(1,1),(1,0,1),(1,0,0,1),(1,0,0,0,1),(1,1,0,1,1),(1,0,0,0,0,1),(0,0,1,1,1,1)]:
                vs = [pat[i]*derives_values[i] for i in range(min(len(pat),len(derives)))]
                if abs(sum(vs)-node_value) < epsilon:
                    for i in range(len(derives_values)):
                        if i>=len(pat) or pat[i]==0:
                            self.logger.debug("!{} X-> {}".format(node.name, derives[i].name))
                            derives[i].remove_derive(node)
                        else:
                            eliminate_extra_link(derives[i])
                    break
        cal_nodes = [v for k,v in nodes.items() if t(k) in fix_cal_node]
        for node in sorted(cal_nodes, reverse=True, key=lambda x: x.presentation_order):
            eliminate_extra_link(node)

    def fix_calc_link_for_parent_subtotal(self, nodes, context_vdic):
        parent_subtotal = {}
        for name in nodes:
            n = nodes[name]
            if name in self._value_dic and n.parent_name in self._value_dic:
                children = parent_subtotal.get(n.parent_name, [])
                parent_subtotal[n.parent_name] = children + [n]

        for parent_name,children in parent_subtotal.items():
            # children make subtotal
            if nodes[parent_name].validate_subtotal(children, context_vdic):
                for child in [x for x in children if x.no_derive()]:
                    self.logger.debug("#{} --> {}:w{}".format(parent_name, child.name,'1'))
                    child.add_derive(nodes[parent_name], '', '0', '1', str(1))
                continue
            # derive children can not make subtotal (内訳であるためSUBTOTALと一致しない)
            derived = [x for x in children if not x.no_derive()]
            if not nodes[parent_name].validate_subtotal(derived, context_vdic) and len(derived)==nodes[parent_name].derived_count:
                for child in derived:
                    self.logger.debug("#{} X-> {}".format(parent_name, child.name))
                    child.remove_derive(nodes[parent_name])

    def eliminate_non_value_calc_leaf(self, nodes):
        def no_current_value(name):
            return all([x.context_ref['id'].startswith('Prior') or x.value=='NaN' for x in self._value_dic[name]])
        # nodes preserves child, parent order (derived, derives order)
        for name in nodes:
            n = nodes[name]
            while n is not None and n.derived_count==0 and len(n.derives)> 0 \
                 and (n.name not in self._value_dic or no_current_value(n.name)):
                derive = n.get_derive()
                n.remove_derive_all()
                n = derive
    
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
            parents = n.get_ascendants()
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

    def flatten_depth(self, depth: pd.Series) -> pd.Series:
        def is_branch(d, dict):
            return any([x.endswith(d) for x in dict if len(x)>len(d)])
        def flatten(d, dict):
            sign = sum([dict.get(d[i:],False) for i in range(len(d))])
            sign_str = ('-' if sign%2==1 else '*') if sign>0 else '+'
            return sign_str + d if not is_branch(d, dict) else d
        depthsign = {d.replace('-',''):d.startswith('-') for d in depth}
        flatten_depth = [flatten(d.replace('-',''), depthsign) for d in depth]
        return pd.Series(flatten_depth, index=depth.index)
    
    def shrink_depth(self, shrink: pd.Series, base: pd.Series) -> pd.Series:
        def conv(d, dict):
            if d[0] in ['+','-']:
                return d
            return dict.get(d, d)
        def d_parent(d):
            return d[2:] if d[0] in '+-' else d[1:]
        shrink_set = set(shrink)
        shrink_child_count = {k: len(list(g)) for k, g in itertools.groupby(sorted(shrink_set, key=d_parent), d_parent)}
        shrink_dict = set(base) - shrink_set
        depthsign = {d[2:]:d[0]+d[2:] for d in shrink_dict if d[0] in '+-' and shrink_child_count.get(d[2:],0)==0}
        shrink_depth = [conv(d, depthsign) for d in shrink]
        return pd.Series(shrink_depth, index=shrink.index)

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
            return self.prohibited['order'] if self.prohibited is not None else 0
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

    def remove_parent(self, parent):
        parents = [x for x in self.parents if x['parent']!=parent]
        if len(parents)!=len(self.parents):
            parent.children_count -= 1
            self.parents = parents

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
        return len(self.get_ascendants())

    @property
    def presentation_order(self):
        parents = [float(x.order) for x in self.get_ascendants()]
        parents.append(float(self.order))
        parents.append(99.)     # short leaf has lower order of the longer leaf. (see flatten_to_schemas)
        return tuple(parents)

    def get_parent(self):
        if self.parents:
            return [x['parent'] for x in self.parents]
        return [self.prohibited] if self.prohibited is not None else []

    def get_ascendants(self):
        parents = []
        ps = self.get_parent()
        while len(ps) != 0 and ps[0] not in parents:
            parents.insert(0, ps[0])
            ps = ps[0].get_parent()
        return parents

    def is_subtotal(self):
        if not self.parents:
            return False
        idx = float(self.order)
        count = self.parents[0]['parent'].children_count
        return False if idx < count else True
    
    def is_sibling(self, target):
        if not self.parents or not target.parents:
            return False
        return self.parents[0]['parent'] == target.parents[0]['parent']

    def add_derive(self, target, use:str, priority:str, order:str, weight:str):
        use_save = use
        target_derives = [x for x in self.derives if x['target']==target]
        for x in target_derives:
            if x['use']=='' and use=='' and x['priority'] >= priority:
                return
            # float(x['order']) may change float(order)
            assert x['use'] in ['prohibited','deleted'] and use=='' and x['priority'] > priority or \
                x['use']=='' and use=='prohibited' and x['priority'] < priority or \
                x['use']=='' and use=='' and x['priority'] < priority
            self.derives.remove(x)
            if x['use']=='prohibited':
                priority = x['priority']
                use_save = 'deleted'
            if use=='prohibited':
                use_save = 'deleted'
        self.derives.append({'target':target, 'use':use_save, 'priority':priority, 'order':order, 'weight':weight})
        if use=='': target.update_derive_count(+1)

    def remove_derive_all(self):
        for x in [x for x in self.derives if x['use']!='prohibited']:
            x['target'].update_derive_count(-1)
        self.derives = []
    
    def remove_derive(self, target):
        derives = [x for x in self.derives if x['target']!=target]
        if len(derives)!=len(self.derives):
            target.update_derive_count(-1)
            self.derives = derives
    
    def remove_derive_children(self, nodes):
        removed = [x for x in nodes if self==x.get_derive()]
        for x in removed:
            x.remove_derive(self)
        return removed
    
    def omit_deleted_derives(self):
        deletes = [x for x in self.derives if x['use']=='deleted']
        for x in deletes:
            x['target'].update_derive_count(-1)
            self.derives.remove(x)
    
    def cvalue(self, context_vdic, nodelist):
        value = cvalue(self, context_vdic)
        calc_values = [float(v.get_weight(self)) * cvalue(v, context_vdic) for v in nodelist if v.has_derive(self)]
        diff = sum(calc_values) - value
        epsilon = epsvalue(value, sum(calc_values), len(calc_values)+2)
        return value, diff, epsilon
    
    def validate_subtotal(self, children, context_vdic):
        result = cvalue(self, context_vdic)
        value = sum([cvalue(v, context_vdic) for v in children])
        return abs(value - result) < epsvalue(result, value, len(children))

    def get_derives(self):
        return sorted([x for x in self.derives if x['use']!='prohibited'], key=lambda x: x['use'])
    
    def get_derive(self):
        derives = self.get_derives()
        return derives[0]['target'] if derives else None

    def update_derive_count(self, diff:int):
        self.derived_count += diff

    def get_derive_chain(self):
        return self._get_derive_chain([])
    def _get_derive_chain(self, path0):
        path = path0 + [self]
        active_chains = [[x['target'], *x['target']._get_derive_chain(path)] for x
            in self.get_derives() if x['target'] not in path]
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
    
    def leading_figures_wo_derive(self, pre_base, context_vdic:Dict[str, ElementValue]):
        def getparent(node):
            return  node.get_parent()[0] if node.get_parent() else None
        subtotal_as_child = self.no_derive() and self.name in context_vdic \
            and getparent(self) and getparent(getparent(self)) in pre_base and getparent(self).no_derive()
        return subtotal_as_child or \
            self.no_derive() and getparent(self) in pre_base and self.name in context_vdic
    
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
        def sum_sign(path):
            signs = [x[1].startswith('-') for x in path]
            pairs = [signs[i] and signs[i+1] for i in range(len(signs)-1)]
            return sum(signs) - 2*sum(pairs)
        path = self.get_derive_subpath()
        sign = sum_sign(path)
        sign_str = ('-' if sign%2==1 else '*') if sign>0 else '+'
        path_str = ''.join([x[0] for x in path])
        return sign_str + path_str if self.derived_count==0 else path_str

def epsilon(value):
    return (1000 if value%10**6 else 10**6 if value%10**9 else 10**9)
def epsvalue(v1, v2, count):
    result = epsilon(v1) if epsilon(v1) < epsilon(v2) else epsilon(v2)
    return result * count
def cvalue(node:Node, vdic):
    return float(vdic[node.name].value) if node.name in vdic else 0
