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
        self._role_dic = {}
        self._context_dic, self._value_dic, self._namespace_dic =\
            ElementValue.read_xbrl_values(self, xbrl_doc.xbrl)

        self.schema_dic = self.taxonomy_repo.get_schema_dicts(self._namespace_dic)
        self.schema_tree = SchemaTree(self, xbrl_doc.find_path('xsd'))

        self.logger = getLogger(__name__)
        self.debug_print = []

    def __reduce_ex__(self, proto):
        return type(self), (self.xbrl_doc, self.taxonomy_repo, )

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

    def read_schema_by_role(self, role_name, use_cal_link=False):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes = {}
        linkbase = self.xbrl_doc.default_linkbase
        self.logger.debug("-------------- Section presentation -----------------")
        for docuri in self.schema_tree.linkbaseRef_iterator(linkbase['doc']):
            self.make_node_tree(nodes, role_name, docuri, linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'])
        if use_cal_link:
            self.logger.debug("--------------- Section calculation -------------------")
            for docuri in self.schema_tree.linkbaseRef_iterator('cal'):
                self.make_node_tree(nodes, role_name, docuri, "calculationLink", "calculationArc", "summation-item")
            self.make_node_tree(nodes, role_name, os.path.join(self.save_dir, "calc-patch.xml"), "calculationLink", "calculationArc", "summation-item")
            self.eliminate_non_value_calc_leaf(nodes)
        return self.flatten_to_schemas(nodes, use_cal_link)

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

                # calc-patch
                if parent["xlink:href"].startswith("calc-patch"):
                    if (get_name(parent) not in nodes or get_name(child) not in nodes) or\
                        nodes[get_name(child)].has_derive(nodes[get_name(parent)]):
                        continue
                    self.debug_print.append("calc-patch applied!!!")
                
                if get_name(child) not in nodes:
                    xsduri = get_absxsduri(docuri, child["xlink:href"])
                    c = ElementSchema.create_from_reference(self, xsduri)
                    nodes[get_name(child)] = Node(c)

                if get_name(parent) not in nodes:
                    xsduri = get_absxsduri(docuri, parent["xlink:href"])
                    p = ElementSchema.create_from_reference(self, xsduri)
                    nodes[get_name(parent)] = Node(p)

                # preserve presentation/calculation struct
                if get_name(child) in self.preserve_struct[arctype]:
                    if get_name(parent) in self.preserve_struct[arctype][get_name(child)]:
                        self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                        if arctype=='presentationArc':
                            nodes[get_name(child)].preserve_parent(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'))
                        if arctype=='calculationArc':
                            nodes[get_name(child)].preserve_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                    else:
                        self.debug_print.append("{} -> {}: o{} p{} {}".format(get_name(parent), get_name(child), arc.get('order','0'), arc.get('priority','0'),arc.get('use','')))
                    continue

                if arctype == "calculationArc":
                    self.logger.debug("{}:{} --> {}:w{} p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("weight",0),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_derive(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'), arc['weight'])
                else:
                    self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_parent(nodes[get_name(parent)], arc.get('use',''), arc.get('priority','0'), arc.get('order','0'))

    preserve_struct = {
        # PL
        'calculationArc': {
            # PL
            'jpfr-t-cte_GrossProfit': 'jpfr-t-cte_OperatingIncome',
            'jpfr-t-cte_SellingGeneralAndAdministrativeExpenses': 'jpfr-t-cte_OperatingIncome',
            'jpfr-t-cte_OperatingIncome': 'jpfr-t-cte_OrdinaryIncome',
            'jpfr-t-cte_NonOperatingIncome': 'jpfr-t-cte_OrdinaryIncome',
            'jpfr-t-cte_NonOperatingExpenses': 'jpfr-t-cte_OrdinaryIncome',
            'jpfr-t-cte_OrdinaryIncome': 'jpfr-t-cte_IncomeBeforeIncomeTaxes',
            'jpfr-t-cte_ExtraordinaryIncome': 'jpfr-t-cte_IncomeBeforeIncomeTaxes',
            'jpfr-t-cte_ExtraordinaryLoss': 'jpfr-t-cte_IncomeBeforeIncomeTaxes',
            'jpfr-t-cte_IncomeBeforeIncomeTaxes': 'jpfr-t-cte_IncomeBeforeMinorityInterests',
            'jpfr-t-cte_IncomeBeforeMinorityInterests': 'jpfr-t-cte_NetIncome',
            # BS
            'jpfr-t-cte_CurrentLiabilities': 'jpfr-t-cte_Liabilities',
            'jpfr-t-cte_NoncurrentLiabilities': 'jpfr-t-cte_Liabilities',
            'jpfr-t-cte_Liabilities': 'jpfr-t-cte_LiabilitiesAndNetAssets',
        },

        # BS
        'presentationArc': {
            # PL
            'jpfr-t-cte_OperatingIncome': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_NonOperatingIncomeAbstract': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_NonOperatingExpensesAbstract': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_OrdinaryIncome': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_ExtraordinaryIncomeAbstract': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_ExtraordinaryLossAbstract': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_IncomeBeforeIncomeTaxes': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            'jpfr-t-cte_NetIncome': 'jpfr-t-cte_StatementsOfIncomeAbstract',
            # BS
            'jpfr-t-cte_AssetsAbstract': ['jpfr-t-cte_BalanceSheetsAbstract'],
                'jpfr-t-cte_CurrentAssetsAbstract': ['jpfr-t-cte_AssetsAbstract'],
                'jpfr-t-cte_CurrentAssets': ['jpfr-t-cte_CurrentAssetsAbstract','jpfr-t-cte_AssetsAbstract'],
                'jpfr-t-cte_NoncurrentAssetsAbstract': ['jpfr-t-cte_AssetsAbstract'],
                'jpfr-t-cte_NoncurrentAssets': ['jpfr-t-cte_NoncurrentAssetsAbstract','jpfr-t-cte_AssetsAbstract'],
                'jpfr-t-cte_Assets':  ['jpfr-t-cte_AssetsAbstract'],
            'jpfr-t-cte_LiabilitiesAbstract': ['jpfr-t-cte_BalanceSheetsAbstract','jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
                'jpfr-t-cte_CurrentLiabilitiesAbstract': ['jpfr-t-cte_LiabilitiesAbstract'],
                'jpfr-t-cte_CurrentLiabilities': ['jpfr-t-cte_CurrentLiabilitiesAbstract','jpfr-t-cte_LiabilitiesAbstract', 'jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
                'jpfr-t-cte_NoncurrentLiabilitiesAbstract': ['jpfr-t-cte_LiabilitiesAbstract'],
                'jpfr-t-cte_NoncurrentLiabilities': ['jpfr-t-cte_NoncurrentLiabilitiesAbstract','jpfr-t-cte_LiabilitiesAbstract','jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
                'jpfr-t-cte_ReservesUnderTheSpecialLawsAbstract1': ['jpfr-t-cte_LiabilitiesAbstract'],
                'jpfr-t-cte_ReservesUnderTheSpecialLawsAbstract2': ['jpfr-t-cte_LiabilitiesAbstract'],
                'jpfr-t-cte_Liabilities': ['jpfr-t-cte_LiabilitiesAbstract', 'jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
            'jpfr-t-cte_NetAssetsAbstract':  ['jpfr-t-cte_BalanceSheetsAbstract','jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
                'jpfr-t-cte_MinorityInterests': ['jpfr-t-cte_NetAssetsAbstract', 'jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
                'jpfr-t-cte_NetAssets': ['jpfr-t-cte_NetAssetsAbstract', 'jpfr-t-ele_LiabilitiesAndNetAssetsAbstractELE'],
        },
        # FC
        'definitionArc': {}
    }

    def eliminate_non_value_calc_leaf(self, nodes):
        # nodes preserves child, parent order (derived, derives order)
        for name in nodes:
            n = nodes[name]
            if n.derived_count==0 and name not in self._value_dic:
                n.remove_derive()

    def flatten_to_schemas(self, nodes, use_cal_link):
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
            if use_cal_link:
                item["depth"] = n.get_derive_path()
                if item['depth'] in ['+','-']: continue
            else:
                item["depth"] = str(len(n.get_derive_chain()))

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
        def calc_value(row, dict):
            def filter(x, base):
                return x['depth'].endswith(base) and x['depth'][0] in ['+','-']
            results = []
            inputs = [x for x in dict if filter(x, row['depth'])]
            contexts = [(x['context'],x['member']) for x in inputs]
            for context in sorted(set(contexts), key=contexts.index):
                item = row.to_dict()
                value = 0
                for input in [x for x in inputs if x['context']==context[0] and x['member']==context[1]]:
                    for k,v in [(k,v) for k,v in input.items() if k not in item]:
                        item[k] = v
                    add = int(input['value']) if input['value']!='NaN' else 0
                    value += add if input['depth'][0] == '+' else -add
                item['value'] = str(value)
                results.append(item)
            return results

        schemas = self.read_schema_by_role(role_link, use_cal_link)
        if len(schemas) == 0:
            return None

        xbrl_data = []
        for i, row in schemas.iterrows():
            tag_name = row['name']
            if tag_name not in self._value_dic:
                xbrl_data += calc_value(row, xbrl_data)
                continue

            results = []
            for value in sorted(self._value_dic[tag_name], reverse=True, key=lambda x: x.context_ref['id']):
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
        if self.debug_print:
            # pd.set_option('display.width', 1000)
            self.logger.info('\n'.join(list(set(self.debug_print))))
            # self.logger.info(xbrl_data[['name','value','depth', 'consolidated','label']])
            self.debug_print = []
        return xbrl_data

    def find_value_names(self, candidates:List[str]) -> List[str]:
        values = []
        for name in candidates:
            values += [x for x in self._value_dic.keys() if name in x]
        return values

    def findv(self, tag):
        id = tag.replace(':', '_')
        return self._value_dic.get(id, [None])[0] # find returns the first element value only.


class Node():

    def __init__(self, element, order=0):
        self.element = element
        self.parent = None
        # self.order = order
        self.priority = ' '
        self.prohibited = None # (parent, order, priority)
        self.parents = []       # e: {'parent':Node, 'order': str, 'priority': str}
        self.children_count = 0
        self.derives = []       # e: {'target':Node, 'use':str, 'priority':str, 'weight':str}
        self.derived_count = 0

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
        prohibited_derives = [x for x in self.derives if x['target']==target and x['use']=='prohibited']
        for p in prohibited_derives:
            target_derives = [x for x in self.derives if x['target']==p['target'] and x['use']!='prohibited']
            if len(target_derives) > 1:
                for x in target_derives:
                    if p['order']==x['order'] and p['priority']>x['priority']:
                        self.derives.remove(p)
                        self.derives.remove(x)
                        p['target'].update_derive_count(-1)

            if target_derives and \
                any([x['order']==p['order']and x['priority']>=p['priority'] for x in target_derives]):
                self.derives.remove(p)
    
    def remove_derive(self):
        for x in [x for x in self.derives if x['use']!='prohibited']:
            x['target'].update_derive_count(-1)
        self.derives = []

    def update_derive_count(self, diff:int):
        self.derived_count += diff
        # if self.derived_count == 0:
        #     actives = [x for x in self.derives if x.get('use','')!='prohibited']
        #     if len(actives) > 0:
        #         assert len(actives) == 1
        #         actives[0]['target'].update_derive_count(-1)
        #         self.derives.remove(actives[0])

    def get_derive_chain(self):
        active_chains = [[x['target'], *x['target'].get_derive_chain()] for x
            in self.derives if x.get('use','')!='prohibited']
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        return sorted_chains[0] if len(sorted_chains) > 0 else []

    def has_derive(self, target):
        derives = [x['target'] for x in self.derives if x['use']!='prohibited']
        if target in derives:
            return True
        for derive in derives:
            if derive.has_derive(target):
                return True
        return False

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
        if len(self.derives)==0 and self.element.data_type in ['monetary']:
            return [(Node.base_node.get_child_index(self),'1')]
        active_chains = [[(x['target'].get_child_index(self),x['weight']), *x['target'].get_derive_subpath()] for x
            in self.derives if x.get('use','')!='prohibited']
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        return sorted_chains[0] if len(sorted_chains) > 0 else []

    @classmethod
    def init_derive_path(cls):
        Node.children_list = {}
        Node.base_node = Node(None)

    def get_derive_path(self):
        path = self.get_derive_subpath()
        sign = any([x[1].startswith('-') for x in path])
        sign_str = '-' if sign else '+'
        path_str = ''.join([x[0] for x in path])
        return sign_str + path_str if self.derived_count==0 else path_str
