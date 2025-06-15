import importlib.util
import os
import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Literal
from enum import Enum, auto
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

    def read_schema_by_role(self, role_name, preserve_cal:Dict, fix_cal_node:List):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes = {}
        linkbase = self.xbrl_doc.default_linkbase
        self.logger.debug("-------------- Section presentation -----------------")
        for docuri in self.schema_tree.linkbaseRef_iterator(linkbase['doc']):
            self.make_node_tree(nodes, role_name, docuri, linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'])
        context_vdic = self.context_value_dic(role_name, nodes)
        self.restructure_presentation(nodes, context_vdic)

        if list(self.schema_tree.linkbaseRef_iterator('cal')) != []:
            self.logger.debug("-------------- Section calculation ------------------")
            preserve_parents = set(sum(preserve_cal.values(),[]))
            for docuri in self.schema_tree.linkbaseRef_iterator('cal'):
                self.make_node_tree(nodes, role_name, docuri, "calculationLink", "calculationArc", "summation-item")
            if fix_cal_node:                
                self.patch_calc_node_tree(context_vdic, nodes, preserve_cal, fix_cal_node)
        return self.flatten_to_schemas(nodes)
    
    def context_value_dic(self, role_name, nodes):
        def most_used_current_context(nodes):
            counter = {}
            for name in [n for n in nodes if n in self._value_dic and self._value_dic[n][0].data_type=='monetary']:
                for context in [x.context_ref['id'] for x in self._value_dic.get(name,[])]:
                    count = counter.get(context,0)
                    counter[context] = count + 1
            if re.search('(?<!Non)Consolidated', role_name):
                consolidated_counter = dict(filter(lambda x: not re.search('NonConsolidated', x[0]), counter.items()))
                if consolidated_counter: counter = consolidated_counter
            not_prior_counter = dict(filter(lambda x: not x[0].startswith('Prior'), counter.items()))
            context = max(not_prior_counter, key=not_prior_counter.get) if not_prior_counter else max(counter, key=counter.get) if counter else ''
            return context
        def select_context(vlist, context):
            list = [x for x in vlist if x.context_ref.get('id','')==context and x.value!='NaN' and x.unit!=''] # isTextBlock: x.unit!=''
            return list[0] if list else None
        context = most_used_current_context(nodes)
        context_value_dic = {k:select_context(v,context) for k,v in self._value_dic.items() if k in nodes and select_context(v,context)}
        self.prepare_epsilon(context_value_dic)
        return context_value_dic

    def prepare_epsilon(self, context_vdic):
        moneys = [x for x in context_vdic.values() if x.data_type=='monetary']
        if not moneys:
            Node.epsilon_value = 0
            return
        eps1 = min([epsilon(float(x.value)) for x in moneys])

        decimals = set([x.decimals for x in moneys])
        eps2 = epsilon2(list(decimals)[0])
        # assert eps1 == eps2
        Node.epsilon_value = eps1
    
    def restructure_presentation(self, nodes, context_vdic):
        self.clean_deleted_presentation(nodes)
        self.mark_subtotal_as_parent(nodes, context_vdic)

    def clean_deleted_presentation(self, nodes):
        for name,node in nodes.items():
            if node.is_deleted_parent_link_only():
                node.remove_children()
    
    def clean_deleted_calculation(self, nodes):
        for name,node in nodes.items():
            node.omit_deleted_derives()

    def mark_subtotal_as_parent(self, nodes, context_vdic):
        parent_children = {}
        for node in nodes.values():
            if node.parent_name is None: continue
            parent_children[node.parent_name] = parent_children.get(node.parent_name, []) + [node]
        for name in parent_children:
            if name not in context_vdic: continue
            if len(parent_children[name]) >= 1:
                nodes[name].mark_subtotal(parent_children[name], context_vdic)

    def patch_calc_node_tree(self, context_value_dic, nodes, preserve_cal:Dict, fix_cal_node):
        self.eliminate_non_value_calc_leaf(nodes, context_value_dic)

        if self.validate_calc_node_tree(context_value_dic, nodes, preserve_cal.keys()):
            return
        
        # preserve_parents = set(sum(preserve_cal.values(),[]))
        # self.fix_not_preserve_link('cal', nodes, preserve_cal, preserve_parents)
        self.clean_deleted_calculation(nodes)
        
        self.fix_calc_link_for_parent_subtotal(nodes, context_value_dic)
        # self.eliminate_non_value_calc_leaf(nodes, context_value_dic)
        self.fix_extra_calc_link(nodes, fix_cal_node, context_value_dic)
        self.fix_missing_calc_link(nodes, fix_cal_node, context_value_dic)

    def validate_calc_node_tree(self, context_value_dic, nodes, cal_keys):
        has_derived = False
        leaf_nodes = []
        for name in nodes:
            # NetIncome = nodes[name].no_derive() but not nodes[name].no_derived()
            if nodes[name].no_derive() and cvalue(nodes[name], context_value_dic) != 0:
                if not leaf_nodes:
                    leaf_nodes = sorted([nodes[n] for n in context_value_dic.keys()], key=lambda x: x.derivation_order)
                ind = leaf_nodes.index(nodes[name])
                if ind+1 < len(leaf_nodes) and not leaf_nodes[ind+1].no_derive():
                    if 'Attributable' in name: continue # jppfs_cor_ProfitLossAttributableToOwnersOfParent is 内訳 of ProfitLoss
                    print('found: ', name)
                    return False
            if nodes[name].has_derived():
                has_derived = True
                if not nodes[name].validate(context_value_dic):
                    print('found: ', name)
                    return False
        return has_derived

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
        for loc in doc.find_all("loc"):
            locs[loc["xlink:label"]] = loc

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
                        if type=='cal' and not nodes[parent].has_derive_chain(preserve_dict[t(name)]):
                            self.logger.debug("{} X-> {}".format(parent,name))
                            nodes[name].remove_derive(nparent)
                        if type=='pre':
                            self.logger.debug("{} X-> {}".format(parent,name))
                            nodes[name].remove_parent(nparent)
            else:
                if type=='cal':
                    nodes[name].omit_deleted_derives()

    def fix_missing_calc_link(self, nodes, fix_cal_node, context_vdic):
        def make_missing_link(derived, orphans):
            if derived is None or not orphans:
                return
            derived_value, diff, epsilon = derived.cvalue(context_vdic)
            if abs(diff) < epsilon and (not orphans or (nmmatch(orphans[0].name, fix_cal_node))): # 1853:2015-08-07: GrossProfit has several gross profits calc link
                return
            orphan_values = [x.cvalue(context_vdic)[0] for x in orphans]
            for pat in [[1], [-1], [1,1], [-1,1], [-1,0,1], [-1,1,1], [0,-1,1], [-1,-1,1], [1,-1,1],
                        [-1,0,0,1], [1,0,0,1], [-1,-1,-1,1],    # -1,-1,-1,1:85950 ジャフコ　　　　　　　　　　2013-04-19 15:15:00: 平成25年3月期 決算短信
                        [-1,1,-1,-1,1], [1,-1,1,-1,1], [-1,1,1,-1,1], [-1,1,1,1,-1,1], [1,-1,1,-1,1,-1,-1,1]]: # [1,-1,1,-1,1,-1,-1,1]:2282:2022-05-10
                if len(pat) > len(orphans): continue
                pat2 = list(pat) + [0] * (len(orphans) - len(pat))
                vs = [pat2[i]*orphan_values[i] for i in range(len(pat2))]
                has_unnecessary_derived = derived.has_derived() and abs(sum(vs)-derived_value) < epsilon
                if abs(sum(vs)+diff) <= epsilon or has_unnecessary_derived:
                    removed = []
                    if has_unnecessary_derived: # 1853:2015-08-07: GrossProfit has several gross profits calc link
                        removed = derived.remove_derive_all_children(nodes.values())
                        if not removed: break
                        removed = [x for x in removed if x not in [orphans[i] for i in range(len(pat2)) if pat2[i]==1]]
                    for i in range(len(pat2)):
                        if pat2[i]!=0:
                            self.logger.debug("!{} --> {}:w{}".format(derived.name, orphans[i].name, pat[i]))
                            orphans[i].add_derive(derived, '', '0', '1', str(pat2[i]))
                            if not nmmatch(orphans[i].name, fix_cal_node) and( len([x for x in pat2[i:] if x==0])>0 or removed):
                                orphans_sub = removed+[orphans[i] for i in range(i,len(pat2)) if pat2[i]==0] if i+1!=len(pat2) \
                                    else orphans[i+1:] if len(orphans)>len(pat2) else []
                                ordered_orphans_sub = sorted(orphans_sub, reverse=True, key=lambda x: x.derivation_order)
                                make_missing_link(orphans[i], ordered_orphans_sub)
                    break
        def test_branchs(node, cal_nodes):
            return node in cal_nodes and not node.no_derive()

        cal_nodes = [v for k,v in nodes.items() if k in context_vdic and nmmatch(k, fix_cal_node) and k in self._value_dic]
        candidates = [v for k,v in nodes.items() if test_branchs(v, cal_nodes) or v.need_to_derive_value(context_vdic, fix_cal_node)]
        ordered_candidates = sorted(candidates, reverse=True, key=lambda x: x.derivation_order)
        for missing in ordered_candidates:
            if nmmatch(missing.name, fix_cal_node):
                derived = missing
                orphans = ordered_candidates[ordered_candidates.index(derived)+1:]
                make_missing_link(derived, orphans)
    
    def fix_extra_calc_link(self, nodes, fix_cal_node, context_vdic):
        def eliminate_extra_link(node):
            derives = sorted([v for v in node.get_derived() if v.name in context_vdic], reverse=True, key=lambda x: x.derivation_order)
            node_value, diff, epsilon = node.cvalue(context_vdic)
            if abs(diff) < epsilon or node_value+diff==0:
                for remove in node.validate_or_remove_derive_children(context_vdic):
                    self.logger.debug("#validate_or_remove_derive_children: {} X-> all".format(remove.name))
                return
            # found extra derives
            derives_values = [v.get_weight(node) * float(context_vdic[v.name].value) for v in derives]
            for pat in [(1,0),(0,0,1,1,1,1),(1,1),(1,0,1),(1,1,1),(1,0,0,1),(1,0,0,0,1),(1,1,0,1,1),(1,0,0,0,0,1),(0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1)]:
                vs = [pat[i]*derives_values[i] for i in range(min(len(pat),len(derives)))]
                if abs(sum(vs)-node_value) < epsilon:
                    for i in range(len(derives_values)):
                        if i>=len(pat) or pat[i]==0:
                            self.logger.debug("!{} X-> {}".format(node.name, derives[i].name))
                            derives[i].remove_derive(node)
                        else:
                            eliminate_extra_link(derives[i])
                    return
            for v in derives: # 1892:2013-02-14
                self.logger.debug("!{} X-> {}".format(node.name, v.name))
                if v.has_derived():
                    eliminate_extra_link(v)
                v.remove_derive(node)
        cal_nodes = [v for k,v in nodes.items() if nmmatch(k, fix_cal_node)]
        for node in sorted(cal_nodes, reverse=True, key=lambda x: x.derivation_order):
            eliminate_extra_link(node)

    def fix_calc_link_for_parent_subtotal(self, nodes, context_vdic):
        def test_lineitems(name, children):
            for parent_name in [name] + [x.parent_name for x in children]:
                if any([parent_name.endswith(x) for x in ['StatementOfIncomeLineItems', 'StatementsOfIncomeAbstract', 'ProfitLossFromContinuingOperationsIFRS']]): # StatementsOfIncomeAbstract:7971:2014-02-07, ProfitLossFromContinuingOperationsIFRS:6191:2021-11-12
                    return True
            return False
        parent_subtotal = self.subtotal_children(nodes, context_vdic)
        for parent_name,children in parent_subtotal.items():
            if context_vdic[parent_name].unit not in ['JPY','USD'] or test_lineitems(parent_name, children):
                continue
            # children make subtotal
            parent_node = nodes[parent_name]
            if parent_node.validate(context_vdic):
                continue
            # parent derives one of children:  64690 放電精密　　　　　　　　　　2012-04-03 16:30:00: 平成24年2月期 決算短信[日本基準](連結)
            if parent_node.is_subtotal() and parent_node.get_derive() in children:
                parent_node.remove_subtotal()
                continue
            if len(children)>1 and nodes[parent_name].compare_subtotal(children, context_vdic)==0:
                for child in [x for x in children if not x.has_derive(nodes[parent_name])]:
                    self.logger.debug("#{} --> {}:w{}".format(parent_name, child.name,'1'))
                    child.add_derive(nodes[parent_name], '', '0', '1', str(1))
                continue

    def subtotal_children(self, nodes, context_vdic):
        _parent_children, parent_children = {}, {}
        for node in nodes.values():
            if node.parent_name is None: continue
            _parent_children[node.parent_name] = _parent_children.get(node.parent_name, []) + [node]
        for name in _parent_children:
            sortedlist = sorted(_parent_children[name], key=lambda x: x.order)
            subtotal = sortedlist[-1]
            if name in context_vdic or subtotal.name in context_vdic:
                parent_children[name] = sortedlist

        subtotal_children = {}
        for name in parent_children:
            if name in context_vdic:
                subtotal_children[name] = parent_children[name]
            else:
                subtotal = parent_children[name].pop(-1)
                if len(parent_children[name])==0: continue
                subtotal_children[subtotal.name] = parent_children[name]
                if nodes[name].parent_name in parent_children and subtotal.get_parent()[0] in parent_children[nodes[name].parent_name]:
                    idx = parent_children[nodes[name].parent_name].index(subtotal.get_parent()[0])
                    parent_children[nodes[name].parent_name].pop(idx)
                    parent_children[nodes[name].parent_name].insert(idx, subtotal)
        return subtotal_children

    def eliminate_non_value_calc_leaf(self, nodes, context_vdic):
        def no_current_value(name):
            return context_vdic.get(name, 'NaN')=='NaN'  # 2813:2013-05-13 all([x.context_ref['id'].startswith('Prior') or x.value=='NaN'
        # nodes preserves child, parent order (derived, derives order)
        for name in nodes:
            n = nodes[name]
            while n is not None and n.no_derived() and not n.no_derive() \
                 and (n.name not in context_vdic or no_current_value(n.name)):
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
                empty_order = 0.0

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


    def read_value_by_role(self, role_link:str, preserve_cal:Dict = {}, fix_cal_node:List = [], scope:str = ""):
        """Read XBRL values in a dataframe which are specified by role and/or context.

        Arguments:
            role_link {str} -- role name or role uri
        Keyword Arguments:
            scope {str} -- context name prefix, eg "Current" for "Current*" (default: {""} for everything)
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

        schemas = self.read_schema_by_role(role_link, preserve_cal, fix_cal_node)
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
            self.logger.info('\n'.join(list(set(self.debug_print))))
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
    epsilon_value = 0

    class Marker(Enum):
        subtotal = auto()
        subtotal_with_fewer_children = auto()
        subtotal_with_extra_children = auto()
        normal_node = auto()

    def __init__(self, element, order=0):
        self.element = element
        self.plinks = DirectedLinks("plink")
        self.clinks = DirectedLinks("clink")
        self.marker:Node.Marker = Node.Marker.normal_node

    @property
    def parents(self):
        return self.get_parent()
    
    @property
    def order(self) -> float:
        plinks = self.plinks.active_src
        if len(plinks) > 1:
            self.debug_print = 'more than two parents found at {}: {}'.format(self.name, [l.l_from.name for l in plinks])
        return plinks[0].order if plinks else 0
    
    def add_parent(self, parent, use:str, priority:str, order:str ):
        self.add_node(self.plinks, parent, use, float(priority), float(order))

    def remove_parent(self, parent):
        self.remove_link(self.plinks.src, parent)
    
    def remove_children(self):
        self.remove_link_all(self.plinks.dst)

    def is_deleted_parent_link_only(self):
        return self.plinks.src and len(self.plinks.active_src)==0

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
        return len(self.plinks.active_dst) == 0
    
    @property
    def depth(self):
        return len(self.get_ascendants())

    @property
    def derivation_order(self):
        try:
            return self.__derivation_order
        except AttributeError:
            parents = [float(x.order) for x in self.get_ascendants()]
            parents.append(float(self.order))
            rest_value = float(self.order) if self.is_leaf else \
                            99. if self.is_subtotal() else 0. # short leaf has lower order of the longer leaf. (see flatten_to_schemas)
            parents = parents + ([rest_value]*(10 - len(parents)))
            self.__derivation_order = tuple(parents)
            return self.__derivation_order

    @property
    def parent_name(self):
        parents = self.get_parent()
        return parents[0].name if parents else None
    
    def get_parent(self):
        return self.plinks.active_src_nodes()

    def get_ascendants(self):
        parents = []
        ps = self.get_parent()
        while len(ps) != 0 and ps[0] not in parents:
            parents.insert(0, ps[0])
            ps = ps[0].get_parent()
        return parents
    
    def links(self, links):
        return self.plinks if links.type=='plink' else self.clinks
    
    def get_prev_sibling(self, links):
        srcs = links.active_src_nodes()
        if not srcs: return None
        siblings = srcs[0].links(links).active_dst_nodes(order=True)
        index = siblings.index(self)
        return siblings[index-1] if index>0 else None

    def get_next_leaf(self):
        plink = next(iter(self.plinks.active_src), None)
        if plink:
            links = [l for l in plink.l_from.plinks.dst if l.order > plink.order]
            if links:
                clink = min(links, key=lambda l: l.order)
                return clink.l_to.get_first_leaf()
            else:
                return plink.l_from.get_next_leaf()
        return None

    def get_first_leaf(self):
        if self.is_leaf:
            return self
        clink = min(self.plinks.active_dst, key=lambda l: l.order)
        return clink.l_to.get_first_leaf()

    def add_derive(self, target, use:str, priority:str, order:str, weight:str):
        if not self.parents or not target.parents:
            return
        if not self.can_add_derive(target):
            # print('bad calc found:{} ==> {}'.format(target.name, self.name))
            return
        # GrossProfit, ProvisionForSalesReturnsGP, GrossProfitNetGP case disables subtotal relationship
        if self.is_subtotal_and_derived_children(target):
            self.marker = Node.Marker.normal_node

        self._add_derive(target, use, priority, order, weight)

    def _add_derive(self, target, use:str, priority:str, order:str, weight:str):
        self.add_node(self.clinks, target, use, float(priority), float(order), float(weight))

    def add_node(self, dlinks, target, use:str, priority:float, order:float, weight:float=-1):
        active_src = [l for l in dlinks.src if l.is_link(target, self, order)]
        if not active_src:
            link = Link(target, self, order, use, priority, weight)
            dlinks.src.append(link)
            target.add_link_dst(dlinks, link)
        else:
            active_src[0].set_properties(use, priority, weight)

    def add_link_dst(self, dlinks, link):
        if dlinks.type == 'clink':
            self.clinks.dst.append(link)
        elif dlinks.type == 'plink':
            self.plinks.dst.append(link)

    def remove_link(self, src_links:List, target):
        for l in [l for l in src_links if l.is_link(target, self)]:
            l.delete()

    def remove_link_all(self, links:List):
        for l in [l for l in links if l.is_active()]:
            l.delete()

    def can_add_derive(self, target):
        if self.is_subtotal():
            return True
        if target.derivation_order < self.derivation_order:
            return False
        return True

    def is_subtotal_and_derived_children(self, target):
        parents = target.get_parent()
        if self.is_subtotal() and parents and parents[0]==self:
            return True
        return False
    
    def remove_subtotal(self):
        if self.parents:
            self.parents[0]['priority'] == 0
            try:
                del self._Node__derivation_order
            except AttributeError:
                pass
    
    def remove_derive_all(self):
        for l in self.clinks.src:
            l.delete()
    
    def remove_derive(self, target):
        for l in [l for l in self.clinks.src if l.is_link(target, self)]:
            l.delete()
    
    def remove_derive_all_children(self, nodes):
        removed = self.clinks.active_dst_nodes()
        for x in removed:
            x.remove_derive(self)
        return removed
    
    def remove_derive_children(self):
        removed = self.clinks.active_dst_nodes()
        if not all([x.no_derived() for x in removed]):
            print('%%%%%% remove_derive_children: {} has derived child, so skip remove'.format(self.name))
            return []
        for x in removed:
            x.remove_derive(self)
        return removed
    
    def omit_deleted_derives(self):
        return
    
    def cvalue(self, context_vdic):
        value = cvalue(self, context_vdic)
        to_target = self.clinks.active_dst_nodes()
        calc_values = [v.get_weight(self) * cvalue(v, context_vdic) for v in to_target]
        diff = sum(calc_values) - value
        epsilon = epsvalue(context_vdic.get(self.name,None), calc_values)
        return value, diff, epsilon
    
    def validate(self, context_vdic):
        value, diff, epsilon = self.cvalue(context_vdic)
        return abs(diff) < epsilon
    
    def validate_or_remove_derive_children(self, context_vdic):
        removed = []
        for node in self.clinks.active_dst_nodes():
            value,diff,e = node.cvalue(context_vdic)
            if abs(diff) > e:
                if node.remove_derive_children():
                    removed.append(node)
        return removed

    def compare_subtotal(self, children, context_vdic):
        def f(v, target):
            return v.get_weight(target) if v.get_weight(target) is not None else 1.0
        if context_vdic[self.name].unit not in ['JPY','USD']: # TODO: it must be len()!=3 or format!='numdotdecimals'
            return False
        result = cvalue(self, context_vdic)
        calc_values = [f(v, self) * cvalue(v, context_vdic) for v in children]
        sum_value = sum(calc_values)
        if abs(sum_value - result) < epsvalue(context_vdic.get(self.name,None), calc_values):
            return 0
        if sum_value - result >= epsvalue(context_vdic.get(self.name,None), calc_values):
            return 1
        return -1

    def get_derives(self):
        return sorted([x for x in self.derives if x['use'] not in ['prohibited','deleted']], key=lambda x: x['use'])
    
    def get_derive(self):
        derives = self.clinks.active_src_nodes()
        return derives[0] if derives else None

    def get_derived(self):
        return self.clinks.active_dst_nodes()

    def update_derive_count(self, diff:int):
        self.derived_count += diff

    def get_derive_chain(self):
        return self._get_derive_chain([])
    def _get_derive_chain(self, path0):
        path = path0 + [self]
        from_target = self.clinks.active_src_nodes()
        active_chains = [[x, *x._get_derive_chain_(path)] for x
            in from_target if x not in path]
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        if len(sorted_chains) > 1: print("!!! get_derive_chain:",sorted_chains)
        return sorted_chains[0] if len(sorted_chains) > 0 else []

    def has_derive(self, target):
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        return derive_links

    def get_weight(self, target) -> float:
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        return derive_links[0].weight if len(derive_links)>0 else None

    def minus_weight(self, target):
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        if derive_links:
            link = derive_links[0]
            link.set_properties(link.use, link.priority, -1)

    def has_derived(self):
        return len(self.clinks.active_dst) > 0
    
    def no_derived(self):
        return len(self.clinks.active_dst) == 0

    def no_derive(self):
        return len(self.clinks.active_src) == 0

    def need_to_derive_value(self, context_vdic:Dict[str, ElementValue], fix_cal_node):
        parents = self.get_parent()
        # omit quasi subtotal that subtotal is not fix_cal_node
        if self.is_subtotal_fewer_children() and not nmmatch(parents[0].name, fix_cal_node): # requires not nmmatch: 64180 日金銭　　　　　　　　　　　2014-02-12 15:30:00: 平成26年3月期 第3四半期決算短信
            return False
        return self.no_derive() and self.name in context_vdic

    def has_derive_chain(self, preserve_parent_names):
        if not self.get_derive_chain():
            return False
        return any([t(x.name) in preserve_parent_names for x in self.get_derive_chain()])
    
    def mark_subtotal(self, children, context_vdic):
        comparison = self.compare_subtotal(children, context_vdic)
        plinks = self.plinks.active_src         # TODO: it is not necessary
        if not plinks:
            return
        if comparison == 0:
            self.marker = Node.Marker.subtotal                      # this is the subtotal as parent
        elif comparison == 1:
            self.marker = Node.Marker.subtotal_with_extra_children  # this is the subtotal but not sum children
        else:
            self.marker = Node.Marker.subtotal_with_fewer_children  # this is the subtotal but not enough children have

    def is_subtotal_fewer_children(self):
        parents = self.get_parent()
        if parents and parents[0].is_subtotal_with_fewer_children():
            return True
        return False
    
    def is_subtotal(self):
        return self.marker in [Node.Marker.subtotal]

    def is_subtotal_with_fewer_children(self):
        return self.marker in [Node.Marker.subtotal_with_fewer_children]

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
        if len(self.clinks.src)==0 and self.element.data_type in ['monetary','perShare']:
            return [(Node.base_node.get_child_index(self),'1')]
        derives = [(l.l_from,str(l.weight)) for l in self.clinks.active_src]
        active_chains = [[(x.get_child_index(self), w), *x._get_derive_subpath(path)] for (x,w)
            in derives if x not in path]
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
            return sum(signs) #- 2*sum(pairs) in some 2024,2023,2022,2021
        path = self.get_derive_subpath()
        sign = sum_sign(path)
        sign_str = ('-' if sign%2==1 else '*') if sign>0 else '+'
        path_str = ''.join([x[0] for x in path])
        return sign_str + path_str if self.no_derived() else path_str

class DirectedLinks():

    def __init__(self, type:Literal["plink","clink"]):
        self.type = type
        self.src = []
        self.dst = []

    @property
    def active_src(self):
        return [l for l in self.src if l.is_active()]

    def active_src_nodes(self):
        return [l.l_from for l in self.src if l.is_active()]

    @property
    def active_dst(self):
        return [l for l in self.dst if l.is_active()]

    def active_dst_nodes(self, order=False):
        if order:
            return [l.l_to for l in sorted(self.dst, key=lambda l: l.order) if l.is_active()]
        return [l.l_to for l in self.dst if l.is_active()]

class Link():

    def __init__(self, l_from:Node, l_to:Node, order:float, use:str, priority:float, weight:float=-1):
        self.l_from = l_from
        self.l_to = l_to
        self.order = order
        self.use = use if use!='optional' else ''
        self.priority = priority
        self.weight = weight
    
    def is_link(self, l_from:Node, l_to:Node, order:float=-1):
        return self.l_from == l_from and self.l_to == l_to \
            and (order<0 or self.order == order)

    def is_active(self):
        return self.use == ''

    def delete(self):
        self.use = 'deleted'

    def set_properties(self, use:str, priority:float, weight:float=-1):
        if self.use=='' and use=='' and self.priority>=priority:
            return
        if self.use=='' and use=='prohibited' and self.priority < priority:
            self.use = 'deleted'
        elif self.use=='prohibited' and use=='' and self.priority > priority:
            self.use = 'deleted'
            priority = self.priority
            weight = self.weight
        elif self.use=='deleted':
            self.use = use if use!='optional' else ''
        self.priority = priority
        self.weight = weight
    
    def to_dict(self):
        result = {
            "from": self.l_from.name,
            "to": self.l_to.name,
            "order": self.order,
            "use": self.use,
            "priority": self.priority
        }
        return result if self.weight < 0 else result | {"weight": self.weight}


def epsilon(value):
    return (1000 if value%10**6 else 10**6 if value%10**9 else 10**9)

def epsilon2(decimal:str):
    return 10**abs(int(decimal))

def epsvalue(ev:ElementValue, values):
    return Node.epsilon_value * (len(values)+2)

def cvalue(node:Node, vdic):
    if node.name not in vdic or '円' in vdic[node.name].value:
        return 0
    return float(vdic[node.name].value)

def subtotal(target, children, vdic):
    def f(v, target):
        return v.get_weight(target) if v.get_weight(target) is not None else 1.0
    calc_values = [f(v, target) * cvalue(v, vdic) for v in children]
    return sum(calc_values)

def t(name:str):
    return name.split('_')[-1]

def nmmatch(tagname:str, matcher:List[str]) -> bool:
    name = t(tagname)
    simple, complex = [],[]
    for x in [x for x in matcher]:
        (simple, complex)[x[0] in '<~>'].append(x)
    if name in simple:
        return True
    return any([nmmatch1(name, x) for x in complex])

import re

def nmmatch1(name:str, matcher:str) -> bool:
    if matcher[0]=='<':
        return name.startswith(matcher[1:])
    if matcher[0]=='>':
        return name.endswith(matcher[1:])
    if matcher[0]=='~':
        return re.search(matcher[1:], name) is not None
    return name==matcher
