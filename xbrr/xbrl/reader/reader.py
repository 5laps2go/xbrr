from __future__ import annotations
from typing import Optional, Literal, Callable, cast

import importlib.util
import os
import math
import itertools
from datetime import date, datetime, timedelta
from pathlib import Path
from enum import Enum, auto
from urllib.parse import urljoin
from logging import getLogger

from bs4 import BeautifulSoup, Tag
from numpy import isin
import pandas as pd
from pandas import DataFrame

from xbrr.base.reader.base_reader import BaseReader
from xbrr.base.reader.xbrl_doc import XbrlDoc
from xbrr.xbrl.reader.element_schema import ElementSchema
from xbrr.xbrl.reader.element_value import ElementValue
from xbrr.xbrl.reader.role_schema import RoleSchema
from xbrr.xbrl.reader.schema_tree import SchemaTree
from xbrr.xbrl.reader.schema_dicts import SchemaDicts
from xbrr.xbrl.reader.taxonomy_repository import TaxonomyRepository


class Reader(BaseReader):

    def __init__(self, xbrl_doc: XbrlDoc, taxonomy_repo:TaxonomyRepository|None=None, save_dir: str = ""):
        super().__init__("edinet", xbrl_doc)
        self.taxonomy_repo = taxonomy_repo if taxonomy_repo is not None\
            else TaxonomyRepository(save_dir)
        self.save_dir = save_dir

        self.context_value_dic:dict[str, list[ElementValue]]
        self._role_dic = {}
        self._context_dic = {}
        self._value_dic:dict[str, list[ElementValue]] = {}
        self._namespace_dic:dict[str, str] = {}
        self.schema_dic:SchemaDicts
        self.schema_tree:SchemaTree
        self._scans_presentation:list[BaseReader.PreTable|BaseReader.PreHeading] = []

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
    def custom_roles(self) -> dict[str,RoleSchema]:
        if len(self._role_dic) == 0:
            linkbase = self.xbrl_doc.default_linkbase
            xml = self.read_uri(self.schema_tree.find_kind_uri(linkbase['doc']))
            link_node, roleRef = self.get_linkbase_tag(xml, linkbase['link_node'], linkbase['roleRef'])
            self._role_dic.update(RoleSchema.read_role_ref(xml, link_node, roleRef, lambda uri: self.read_uri(uri)))
        return self._role_dic

    @property
    def namespaces(self) -> dict[str, str]:
        return self._namespace_dic

    def presentation_version(self) -> str:
        return self.schema_tree.presentation_version()
    
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

    # def get_role(self, role_name) -> RoleSchema:
    #     if '/' in role_name:
    #         role_name = role_name.rsplit('/', 1)[-1]
    #     return self.custom_roles[role_name]

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
    
    def get_linkbase_tag(self, doc:BeautifulSoup, *args) -> tuple[str,str]:
        ns_prefixes = {v: k for k,v in doc._namespaces.items()}
        if (link_prefix:=ns_prefixes.get("http://www.xbrl.org/2003/linkbase")) is not None:
            return cast(tuple[str,str], ("{}:{}".format(link_prefix, arg) for arg in args))
        return args
    
    def get_label_uri(self, xsduri:str) -> str:
        "get the uri of the label for the xsd uri"
        laburi = self.schema_tree.find_kind_uri('lab', xsduri)
        return laburi

    @property
    def role_decision_info(self) -> list[BaseReader.PreTable|BaseReader.PreHeading]:
        if len(self._scans_presentation)==0:
            self._scans_presentation = self.__scan_presentation()
        return self._scans_presentation
    
    def __scan_presentation(self) -> list[BaseReader.PreTable|BaseReader.PreHeading]:
        scans:list[BaseReader.PreTable|BaseReader.PreHeading] = []
        linkbase = self.xbrl_doc.default_linkbase
        for docuri in self.schema_tree.linkbaseRef_iterator(linkbase['doc']):
            if docuri.startswith('http'):
                # for deciding presentation role, skip taxonomy presentation linkbases
                continue
            doc = self.read_uri(docuri)
            link_node, arc_node = self.get_linkbase_tag(doc, linkbase['link_node'], linkbase['arc_node'])
            for link in doc.find_all(link_node):
                assert isinstance(link, Tag)
                role_name = cast(str,link["xlink:role"]).split('#')[-1]
                # find Axis
                table = ''
                cons_noncons = ''
                locs_after_cons = 5
                for loc in link.find_all("loc"):
                    if table and cons_noncons and locs_after_cons <= 0:
                        break
                    assert isinstance(loc, Tag)
                    href = cast(str,loc["xlink:href"])
                    item = href.split("#")[-1].split("_")[-1]
                    if item.endswith("Table"):
                        table = item
                    if item.endswith("ConsolidatedAxis"):
                        pass
                    if item.endswith("ConsolidatedMember"):
                        cons_noncons = item if not cons_noncons else "ConsNonconsMember"
                    if cons_noncons:
                        locs_after_cons = locs_after_cons - 1
                    # tse-t-ed="http://www.xbrl.tdnet.info/jp/br/tdnet/t/ed/2007-06-30
                    if item.endswith("IncomeStatementsInformationAbstract"):
                        table = item
                        cons_noncons = role_name.split('/')[-1] + "Member"
                    # role_name=="http://www.xbrl.tdnet.info/jp/tse/tdnet/role/RoleAttachedDocument"
                    #             US-GAAP? http://disclosure.edinet-fsa.go.jp/role/jpcrp/rol_CabinetOfficeOrdinanceOnDisclosureOfCorporateInformationEtcFormNo3AnnualSecuritiesReport
                    if href.endswith("TextBlock"):
                        tolabel = cast(str,loc["xlink:label"])
                        if not (arc:=link.find(arc_node, attrs={"xlink:to":tolabel})): continue
                        assert isinstance(arc, Tag)
                        headingloc = link.find("loc", attrs={"xlink:label": arc["xlink:from"]})
                        assert isinstance(headingloc, Tag)
                        heading = cast(str,headingloc["xlink:href"]).split("#")[-1].split("_")[-1]
                        if not heading.endswith("Heading"): continue
                        blockitem = href.split("#")[-1]
                        consolidated = "NonConsolidated" if "NonConsolidated" in heading else "Consolidated" if "Consolidated" in heading else ""
                        if consolidated: heading = heading.split(consolidated)[-1]
                        scans.append(Reader.PreHeading(heading=heading, cons_nocons=consolidated, xlink_href=blockitem))
                scans.append(Reader.PreTable(table=table, cons_nocons=cons_noncons, xlink_role=role_name)) # type: ignore
        return scans

    def read_schema_by_role(self, role_link:str, fix_cal_node:list[str]=[], report_start:Optional[date]=None, report_end:Optional[date]=None) -> DataFrame:
        assert role_link.startswith("http"), "role must be full uri: {}".format(role_link)
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes:dict[str, Node] = {}
        linkbase = self.xbrl_doc.default_linkbase
        self.logger.debug("-------------- Section presentation -----------------")
        for docuri in self.schema_tree.linkbaseRef_iterator(linkbase['doc']):
            self.make_node_tree(nodes, role_link, docuri, linkbase['link_node'], linkbase['arc_node'], linkbase['arc_role'])
        self.context_value_dic = self.select_value_dic(nodes, role_link)
        current_vdic = self.current_value_dic(report_start, report_end)
        self.restructure_presentation(nodes, current_vdic)

        if list(self.schema_tree.linkbaseRef_iterator('cal')) != []:
            self.logger.debug("-------------- Section calculation ------------------")
            for docuri in self.schema_tree.linkbaseRef_iterator('cal'):
                self.make_node_tree(nodes, role_link, docuri, "calculationLink", "calculationArc", "summation-item")
            if fix_cal_node:                
                self.patch_calc_node_tree(current_vdic, nodes, fix_cal_node)
        return self.flatten_to_schemas(nodes)
    
    def select_value_dic(self, nodes:dict[str, Node], role_link:str) -> dict[str, list[ElementValue]]:
        # key: element name, which includes namespace prefix following _
        # list[ElementValue]: Current, Prior1, Prior2 order of ElementValues in this role context
        def axis_member(dict:dict[str,str], value:ElementValue) -> bool:
            # assign consolidatedMember at the case not provided cons-noncons Axis, if it is required
            contexts = {k:v for k,v in value.context_ref.items() if k.endswith("Axis")}
            if (consaxiss:=[k for k in dict if k.startswith("Consolidated")]):
                if not any(["Consolidated" in k for k in contexts]):
                    contexts[consaxiss[0]] = "ConsolidatedMember"
            if set(dict.keys()) == set([x for x in contexts.keys() if x.endswith("Axis")]):
                for key in dict:
                    if contexts[key] not in dict[key]:
                        return False
                # non-axis comparison like IncomeQuarterly, IncomeYTD
                if any([period in role_link for period in ["YearToQuarterEnd","QuarterPeriod"]]) and "QuarterDuration" in value.context_ref['id']:
                    return False
                if any([period in role_link for period in ["QuarterPeriod","IncomeQuater"]]) and "YTDDuration" in value.context_ref['id']:
                    return False
                return True
            return False
        axisdict = {}
        for name in [nm for nm in nodes if nm.endswith("Member")]:
            member = name.split('_')[-1]
            if not (axiss:=[n for n in nodes[name].get_parent() if n.name.endswith("Axis")]): continue
            axis = axiss[0].name.split('_')[-1]
            axisdict[axis] = axisdict.get(axis,[]) + [member]
        # old style presentation does not have cons-noncons Axis, but value context may have cons-noncons Axis.
        if not axisdict and role_link.startswith("http://info.edinet-fsa.go.jp/jp/fr/gaap/role/"):
            consaxis = "ConsolidatedOrNonConsolidatedAxis" if 'edinet' in role_link else "ConsolidatedNonconsolidatedAxis"
            axisdict[consaxis] = "NonConsolidatedMember" if "NonConsolidated" in role_link else "ConsolidatedMember"

        context_value_dic:dict[str, list[ElementValue]] = {}
        for key in nodes:
            if key not in self._value_dic or not (values:=[v for v in self._value_dic[key] if axis_member(axisdict,v)]):
                continue
            context_value_dic[key] = sorted(values, key=lambda x: x.context_ref['id']) # Current, Prior1, Prior2 order
        return context_value_dic

    def current_value_dic(self, report_start:Optional[date]=None, report_end:Optional[date]=None) -> dict[str,ElementValue]:
        # filter context by period_start and period_end
        def filter_period(vlist:list[ElementValue]) -> Optional[ElementValue]:
            for v in vlist:
                if 'period_start' in v.context_ref:
                    if v.context_ref['period_start'] == period_start and \
                        v.context_ref['period'] == period_end:
                        return v
                elif v.context_ref['period'] == period_end: # and v.value!='NaN' and v.unit!='':
                    return v
            return None

        current_vdic:dict[str,ElementValue] = {}
        context_ids = set([v.context_ref['id'] for vlist in self.context_value_dic.values() for v in vlist])
        if any(['period_start' in self._context_dic[x] for x in context_ids]):
            context_ids = sorted([x for x in context_ids if 'period_start' in self._context_dic[x]], key=lambda x: self._context_dic[x]['period_start'], reverse= False)
        sorted_context_ids = sorted(context_ids, key=lambda x: self._context_dic[x]['period'], reverse=True)
        assert sorted_context_ids, "no context ids found"

        period_start = "2009-01-01"
        if 'period_start' in self._context_dic[sorted_context_ids[0]]:
            if report_start is not None and report_start.strftime("%Y-%m-%d") != self._context_dic[sorted_context_ids[0]]['period_start']:
                self.logger.info("report_start {} does not match period_start {}: {}".format(
                    report_start.strftime("%Y-%m-%d"), self._context_dic[sorted_context_ids[0]]['period_start'], sorted_context_ids))
            if len(sorted_context_ids) > 1:
                assert not (sorted_context_ids[0].startswith('Prior') and sorted_context_ids[1].startswith('Current')), "invalid context ids: {}".format(sorted_context_ids)
            period_start = self._context_dic[sorted_context_ids[0]]['period_start']
        if report_end is not None and report_end.strftime("%Y-%m-%d") != self._context_dic[sorted_context_ids[0]]['period']:
            self.logger.info("report_end {} does not match period_end {}: {}".format(
                report_end.strftime("%Y-%m-%d"), self._context_dic[sorted_context_ids[0]]['period'], sorted_context_ids))
            if len(sorted_context_ids) > 1:
                assert not (sorted_context_ids[0].startswith('Prior') and sorted_context_ids[1].startswith('Current')), "invalid context ids: {}".format(sorted_context_ids)
        period_end = self._context_dic[sorted_context_ids[0]]['period']
        
        current_vdic = {k:v for (k,vlist) in self.context_value_dic.items() if (v:=filter_period(vlist))}
        self.prepare_epsilon(current_vdic)
        return current_vdic

    def prepare_epsilon(self, current_vdic:dict[str,ElementValue]):
        moneys = [x for x in current_vdic.values() if x.data_type=='monetary' and x.value!='NaN']
        if not moneys:
            Node.epsilon_value = 0
            return
        eps1 = min([epsilon(float(x.value)) for x in moneys])

        # decimals = set([x.decimals for x in moneys if x.decimals!=''])
        # eps2 = epsilon2(list(decimals)[0])
        # assert eps1 == eps2
        Node.epsilon_value = eps1
    
    def restructure_presentation(self, nodes:dict[str,Node], current_vdic:dict[str,ElementValue]):
        self.clean_deleted_presentation(nodes)
        self.mark_subtotal_as_parent(nodes, current_vdic)

    def clean_deleted_presentation(self, nodes:dict[str,Node]):
        for name,node in nodes.items():
            if node.is_deleted_parent_link_only():
                node.remove_children()
    
    def clean_deleted_calculation(self, nodes:dict[str,Node]):
        for name,node in nodes.items():
            node.omit_deleted_derives()

    def mark_subtotal_as_parent(self, nodes:dict[str,Node], current_vdic:dict[str,ElementValue]):
        parent_children = {}
        for node in nodes.values():
            if node.parent_name is None: continue
            parent_children[node.parent_name] = parent_children.get(node.parent_name, []) + [node]
        for name in parent_children:
            if name not in current_vdic: continue
            if len(parent_children[name]) >= 1:
                nodes[name].mark_subtotal(parent_children[name], current_vdic)

    def patch_calc_node_tree(self, context_value_dic:dict[str,ElementValue], nodes:dict[str,Node], fix_cal_node:list[str]):
        self.eliminate_non_value_calc_leaf(nodes, context_value_dic)

        if self.validate_calc_node_tree(context_value_dic, nodes):
            return
        
        # preserve_parents = set(sum(preserve_cal.values(),[]))
        # self.fix_not_preserve_link('cal', nodes, preserve_cal)
        self.clean_deleted_calculation(nodes)
        
        self.fix_calc_link_for_parent_subtotal(nodes, context_value_dic)
        # self.eliminate_non_value_calc_leaf(nodes, context_value_dic)
        self.fix_extra_calc_link(nodes, fix_cal_node, context_value_dic)
        self.fix_missing_calc_link(nodes, fix_cal_node, context_value_dic)

    def validate_calc_node_tree(self, context_value_dic:dict[str,ElementValue], nodes:dict[str,Node]) -> bool:
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
                    self.logger.debug("invalid calc node tree caused by {}".format(name))
                    return False
            if nodes[name].has_derived():
                has_derived = True
                if not nodes[name].validate(context_value_dic):
                    self.logger.debug("invalid calc node tree caused by {}".format(name))
                    return False
        return has_derived

    def make_node_tree(self, nodes:dict[str,Node], role_link:str, docuri:str, link_node:str, arc_node:str, arc_role:str):
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
            if not isinstance(loc, Tag): continue
            locs[loc["xlink:label"]] = loc

        for role in doc.find_all(link_node, {"xlink:role": role_link}):
            if not isinstance(role, Tag): continue
            for i, arc in enumerate(role.find_all(arc_node, recursive=False)):
                if not isinstance(arc, Tag): continue
                assert str(arc["xlink:arcrole"]).split('/')[-1] in ['parent-child','summation-item','domain-member', 'dimension-domain', 'all', 'hypercube-dimension']
                # if not str(arc["xlink:arcrole"]).endswith(arc_role):
                #     continue

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
                    self.logger.debug("{}:{} --> {}:w{} p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("weight","0"),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_derive(nodes[get_name(parent)], str(arc.get('use','')), str(arc.get('priority','0')), str(arc.get('order','0')), str(arc['weight']))
                else:
                    self.logger.debug("{}:{} --> {}:p{} o{} {}".format(nodes[get_name(parent)].label,get_name(parent),get_name(child),arc.get("priority","0"),arc.get("order","0"),arc.get("use",'')))
                    nodes[get_name(child)].add_parent(nodes[get_name(parent)], str(arc.get('use','')), str(arc.get('priority','0')), str(arc.get('order','0')))

    def fix_not_preserve_link(self, type:Literal['cal','pre'], nodes:dict[str,Node], preserve_dict:dict):
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

    def fix_missing_calc_link(self, nodes:dict[str,Node], fix_cal_node:list[str], current_vdic:dict[str,ElementValue]):
        def make_missing_link(derived, orphans):
            if derived is None or not orphans:
                return
            derived_value, diff, epsilon = derived.cvalue(current_vdic)
            if abs(diff) < epsilon and (not orphans or (nmmatch(orphans[0].name, fix_cal_node))): # 1853:2015-08-07: GrossProfit has several gross profits calc link
                return
            orphan_values = [cvalue0(x, current_vdic) for x in orphans]
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

        cal_nodes = [v for k,v in nodes.items() if k in current_vdic and nmmatch(k, fix_cal_node)]
        candidates = [v for k,v in nodes.items() if test_branchs(v, cal_nodes) or v.need_to_derive_value(current_vdic, fix_cal_node)]
        ordered_candidates = sorted(candidates, reverse=True, key=lambda x: x.derivation_order)
        for missing in ordered_candidates:
            if nmmatch(missing.name, fix_cal_node):
                derived = missing
                orphans = ordered_candidates[ordered_candidates.index(derived)+1:]
                make_missing_link(derived, orphans)
    
    def fix_extra_calc_link(self, nodes:dict[str,Node], fix_cal_node:list[str], current_vdic:dict[str,ElementValue]):
        def eliminate_extra_link(node):
            derives = sorted([v for v in node.get_derived() if v.name in current_vdic], reverse=True, key=lambda x: x.derivation_order)
            node_value, diff, epsilon = node.cvalue(current_vdic)
            if abs(diff) < epsilon or node_value+diff==0:
                for remove in node.validate_or_remove_derive_children(current_vdic):
                    self.logger.debug("#validate_or_remove_derive_children: {} X-> all".format(remove.name))
                return
            # found extra derives
            derives_values = [v.get_weight(node) * float(current_vdic[v.name].value) for v in derives]
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

    def fix_calc_link_for_parent_subtotal(self, nodes:dict[str, Node], current_vdic:dict[str,ElementValue]):
        def test_lineitems(name, children):
            for parent_name in [name] + [x.parent_name for x in children]:
                if any([parent_name.endswith(x) for x in ['StatementOfIncomeLineItems', 'StatementsOfIncomeAbstract', 'ProfitLossFromContinuingOperationsIFRS']]): # StatementsOfIncomeAbstract:7971:2014-02-07, ProfitLossFromContinuingOperationsIFRS:6191:2021-11-12
                    return True
            return False
        parent_subtotal = self.subtotal_children(nodes, current_vdic)
        for parent_name,children in parent_subtotal.items():
            if current_vdic[parent_name].unit not in ['JPY','USD'] or test_lineitems(parent_name, children):
                continue
            # children make subtotal
            parent_node = nodes[parent_name]
            if parent_node.validate(current_vdic):
                continue
            # parent derives one of children:  64690 放電精密　　　　　　　　　　2012-04-03 16:30:00: 平成24年2月期 決算短信[日本基準](連結)
            if parent_node.is_subtotal() and parent_node.get_derive() in children:
                parent_node.remove_subtotal()
                continue
            if len(children)>1 and nodes[parent_name].compare_subtotal(children, current_vdic)==0:
                for child in [x for x in children if not x.has_derive(nodes[parent_name])]:
                    self.logger.debug("#{} --> {}:w{}".format(parent_name, child.name,'1'))
                    child.add_derive(nodes[parent_name], '', '0', '1', str(1))
                continue

    def subtotal_children(self, nodes:dict[str,Node], current_vdic:dict[str,ElementValue]) -> dict[str,list[Node]]:
        _parent_children, parent_children = {}, {}
        for node in nodes.values():
            if node.parent_name is None: continue
            _parent_children[node.parent_name] = _parent_children.get(node.parent_name, []) + [node]
        for name in _parent_children:
            sortedlist = sorted(_parent_children[name], key=lambda x: x.order)
            subtotal = sortedlist[-1]
            if name in current_vdic or subtotal.name in current_vdic:
                parent_children[name] = sortedlist

        subtotal_children = {}
        for name in parent_children:
            if name in current_vdic:
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

    def eliminate_non_value_calc_leaf(self, nodes:dict[str,Node], current_vdic:dict[str,ElementValue]):
        def no_current_value(name):
            return current_vdic.get(name, ElementValue.NaN).value == 'NaN'  # 2813:2013-05-13 all([x.context_ref['id'].startswith('Prior') or x.value=='NaN'
        # nodes preserves child, parent order (derived, derives order)
        for name in nodes:
            n = nodes[name]
            while n is not None and n.no_derived() and not n.no_derive() \
                 and n.name not in current_vdic:
                derive = n.get_derive()
                n.remove_derive_all()
                n = derive
    
    def flatten_to_schemas(self, nodes:dict[str,Node]) -> DataFrame:
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
            if n.is_leaf and name0 not in self.context_value_dic:
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

    def read_value_by_role(self, role_link:str, fix_cal_node:list = [], scope:str = "", report_start:Optional[date]=None, report_end:Optional[date]=None) -> DataFrame:
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

        schemas = self.read_schema_by_role(role_link, fix_cal_node, report_start, report_end)
        if len(schemas) == 0:
            return pd.DataFrame()
        
        xbrl_data = []
        for i, row in schemas.iterrows():
            tag_name = row['name']
            row['name'] = ':'.join(tag_name.rsplit('_', 1))
            if tag_name not in self.context_value_dic:
                xbrl_data += calc_value(row, xbrl_data)
                continue

            results = []
            for value in sorted(self.context_value_dic[tag_name], reverse=True, key=lambda x: x.context_ref['id']):
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

    def find_value_names(self, candidates:list[str]) -> list[str]:
        values = []
        for name in candidates:
            values += [x for x in self._value_dic.keys() if name in x]
        return values
    
    def find_value_name(self, findop:Callable[[str], bool]) -> str:
        return next(filter(findop, self._value_dic.keys()), '') # '' as Not Found

    def findv(self, name) -> Optional[ElementValue]:
        id = name.replace(':', '_')
        return self._value_dic.get(id, [None])[0] # find returns the first element value only.


class Node():
    epsilon_value = 0

    @classmethod
    def init_derive_path(cls):
        Node.children_list = {}
        Node.base_node = Node(ElementSchema())

    class Marker(Enum):
        subtotal = auto()
        subtotal_with_fewer_children = auto()
        subtotal_with_extra_children = auto()
        normal_node = auto()

    def __init__(self, element:ElementSchema):
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
    
    def add_parent(self, parent:Node, use:str, priority:str, order:str ):
        self.add_node(self.plinks, parent, use, float(priority), float(order))

    def remove_parent(self, parent:Node):
        self.remove_link(self.plinks.src, parent)
    
    def remove_children(self):
        self.remove_link_all(self.plinks.dst)

    def is_deleted_parent_link_only(self):
        return self.plinks.src and len(self.plinks.active_src)==0

    @property
    def name(self) -> str:
        return self.element.name

    @property
    def label(self) -> str:
        return self.element.label

    @property
    def reference(self) -> str:
        return self.element.reference

    @property
    def is_leaf(self) -> bool:
        return len(self.plinks.active_dst) == 0
    
    @property
    def depth(self) -> int:
        return len(self.get_ascendants())

    @property
    def derivation_order(self) -> tuple[float, ...]:
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
    def parent_name(self) -> Optional[str]:
        parents = self.get_parent()
        return parents[0].name if parents else None
    
    def get_parent(self) -> list[Node]:
        return self.plinks.active_src_nodes()

    def get_ascendants(self) -> list[Node]:
        parents = []
        ps = self.get_parent()
        while len(ps) != 0 and ps[0] not in parents:
            parents.insert(0, ps[0])
            ps = ps[0].get_parent()
        return parents
    
    def links(self, links:DirectedLinks) -> DirectedLinks:
        return self.plinks if links.type=='plink' else self.clinks
    
    def get_prev_sibling(self, links) -> Optional[Node]:
        srcs = links.active_src_nodes()
        if not srcs: return None
        siblings = srcs[0].links(links).active_dst_nodes(order=True)
        index = siblings.index(self)
        return siblings[index-1] if index>0 else None

    def get_next_leaf(self) -> Optional[Node]:
        plink = next(iter(self.plinks.active_src), None)
        if plink:
            links = [l for l in plink.l_from.plinks.dst if l.order > plink.order]
            if links:
                clink = min(links, key=lambda l: l.order)
                return clink.l_to.get_first_leaf()
            else:
                return plink.l_from.get_next_leaf()
        return None

    def get_first_leaf(self) -> Node:
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

    def _add_derive(self, target:Node, use:str, priority:str, order:str, weight:str):
        self.add_node(self.clinks, target, use, float(priority), float(order), float(weight))

    def add_node(self, dlinks:DirectedLinks, target:Node, use:str, priority:float, order:float, weight:float=-1):
        active_src = [l for l in dlinks.src if l.is_link(target, self, order)]
        if not active_src:
            link = Link(target, self, order, use, priority, weight)
            dlinks.src.append(link)
            target.add_link_dst(dlinks, link)
        else:
            active_src[0].set_properties(use, priority, weight)

    def add_link_dst(self, dlinks:DirectedLinks, link:Link):
        if dlinks.type == 'clink':
            self.clinks.dst.append(link)
        elif dlinks.type == 'plink':
            self.plinks.dst.append(link)

    def remove_link(self, src_links:list[Link], target:Node):
        for l in [l for l in src_links if l.is_link(target, self)]:
            l.delete()

    def remove_link_all(self, links:list[Link]):
        for l in [l for l in links if l.is_active()]:
            l.delete()

    def can_add_derive(self, target:Node) -> bool:
        if self.is_subtotal():
            return True
        if target.derivation_order < self.derivation_order:
            return False
        return True

    def is_subtotal_and_derived_children(self, target:Node) -> bool:
        parents = target.get_parent()
        if self.is_subtotal() and parents and parents[0]==self:
            return True
        return False
    
    def remove_subtotal(self):
        self.marker = Node.Marker.normal_node
    
    def remove_derive_all(self):
        for l in self.clinks.src:
            l.delete()
    
    def remove_derive(self, target:Node):
        for l in [l for l in self.clinks.src if l.is_link(target, self)]:
            l.delete()
    
    def remove_derive_all_children(self, nodes:list[Node]):
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
    
    def cvalue(self, current_vdic:dict[str,ElementValue]) -> tuple[float,float,int]:
        value = cvalue(self, current_vdic)
        to_target = self.clinks.active_dst_nodes()
        calc_values = subtotal(self, to_target, current_vdic)
        diff = sum(calc_values) - value
        epsilon = epsvalue(current_vdic.get(self.name,None), calc_values)
        return value, diff, epsilon
    
    def validate(self, current_vdic:dict[str, ElementValue]) -> bool:
        value, diff, epsilon = self.cvalue(current_vdic)
        return abs(diff) < epsilon
    
    def validate_or_remove_derive_children(self, current_vdic:dict[str, ElementValue]):
        removed = []
        for node in self.clinks.active_dst_nodes():
            value,diff,e = node.cvalue(current_vdic)
            if abs(diff) > e:
                if node.remove_derive_children():
                    removed.append(node)
        return removed

    def compare_subtotal(self, children:list[Node], current_vdic:dict[str, ElementValue]) -> int:
        if current_vdic[self.name].unit not in ['JPY','USD']: # TODO: it must be len()!=3 or format!='numdotdecimals'
            return False
        result = cvalue(self, current_vdic)
        calc_values = subtotal(self, children, current_vdic)
        sum_value = sum(calc_values)
        if abs(sum_value - result) < epsvalue(current_vdic.get(self.name,None), calc_values):
            return 0
        if sum_value - result >= epsvalue(current_vdic.get(self.name,None), calc_values):
            return 1
        return -1

    def get_derive(self) -> Optional[Node]:
        derives = self.clinks.active_src_nodes()
        return derives[0] if derives else None

    def get_derived(self) -> list[Node]:
        return self.clinks.active_dst_nodes()

    def update_derive_count(self, diff:int):
        self.derived_count += diff

    def get_derive_chain(self) -> list[Node]:
        return self._get_derive_chain([])
    def _get_derive_chain(self, path0:list[Node]) -> list[Node]:
        path = path0 + [self]
        from_target = self.clinks.active_src_nodes()
        active_chains = [[x, *x._get_derive_chain(path)] for x
            in from_target if x not in path]
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        if len(sorted_chains) > 1: print("!!! get_derive_chain:",sorted_chains)
        return sorted_chains[0] if len(sorted_chains) > 0 else []

    def has_derive(self, target:Node) -> list[Link]:
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        return derive_links

    def get_weight(self, target:Node) -> Optional[float]:
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        return derive_links[0].weight if len(derive_links)>0 else None

    def minus_weight(self, target:Node):
        derive_links = [l for l in self.clinks.active_src if l.is_link(target, self)]
        if derive_links:
            link = derive_links[0]
            link.set_properties(link.use, link.priority, -1)

    def has_derived(self) -> bool:
        return len(self.clinks.active_dst) > 0
    
    def no_derived(self) -> bool:
        return len(self.clinks.active_dst) == 0

    def no_derive(self) -> bool:
        return len(self.clinks.active_src) == 0

    def need_to_derive_value(self, current_vdic:dict[str, ElementValue], fix_cal_node:list[str]):
        parents = self.get_parent()
        # omit quasi subtotal that subtotal is not fix_cal_node
        if self.is_subtotal_fewer_children() and not nmmatch(parents[0].name, fix_cal_node): # requires not nmmatch: 64180 日金銭　　　　　　　　　　　2014-02-12 15:30:00: 平成26年3月期 第3四半期決算短信
            return False
        return self.no_derive() and self.name in current_vdic

    def has_derive_chain(self, preserve_parent_names:list[str]) -> bool:
        if not self.get_derive_chain():
            return False
        return any([t(x.name) in preserve_parent_names for x in self.get_derive_chain()])
    
    def mark_subtotal(self, children:list[Node], current_vdic:dict[str, ElementValue]):
        comparison = self.compare_subtotal(children, current_vdic)
        plinks = self.plinks.active_src         # TODO: it is not necessary
        if not plinks:
            return
        if comparison == 0:
            self.marker = Node.Marker.subtotal                      # this is the subtotal as parent
        elif comparison == 1:
            self.marker = Node.Marker.subtotal_with_extra_children  # this is the subtotal but not sum children
        else:
            self.marker = Node.Marker.subtotal_with_fewer_children  # this is the subtotal but not enough children have

    def is_subtotal_fewer_children(self) -> bool:
        parents = self.get_parent()
        if parents and parents[0].is_subtotal_with_fewer_children():
            return True
        return False
    
    def is_subtotal(self) -> bool:
        return self.marker in [Node.Marker.subtotal]

    def is_subtotal_with_fewer_children(self) -> bool:
        return self.marker in [Node.Marker.subtotal_with_fewer_children]

    def get_child_index(self, child) -> str:
        children = Node.children_list.get(self, [])
        if child not in children:
            children.append(child)
            Node.children_list[self] = children
        child_index = children.index(child)
        return '123456789abcdefghijklmnopqrstuvwxyz'[child_index] if child_index < 35 else '0'

    def get_derive_subpath(self) -> list[tuple[str,Literal['1','-1']]]:
        return self._get_derive_subpath([])
    def _get_derive_subpath(self, path0) -> list[tuple[str,Literal['1','-1']]]:
        path = path0 + [self]
        if len(self.clinks.src)==0 and self.element.data_type in ['monetary','perShare']:
            return [(Node.base_node.get_child_index(self),'1')]
        derives = [(l.l_from,str(l.weight)) for l in self.clinks.active_src]
        active_chains = [[(x.get_child_index(self), w), *x._get_derive_subpath(path)] for (x,w)
            in derives if x not in path]
        sorted_chains = sorted(active_chains, key=len, reverse=True)
        return sorted_chains[0] if len(sorted_chains) > 0 else [(Node.base_node.get_child_index(self),'1')]

    def get_derive_path(self) -> str:
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
        self.src:list[Link] = []
        self.dst:list[Link] = []

    @property
    def active_src(self) -> list[Link]:
        return [l for l in self.src if l.is_active()]

    def active_src_nodes(self) -> list[Node]:
        return [l.l_from for l in self.src if l.is_active()]

    @property
    def active_dst(self) -> list[Link]:
        return [l for l in self.dst if l.is_active()]

    def active_dst_nodes(self, order=False) -> list[Node]:
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
    
    def is_link(self, l_from:Node, l_to:Node, order:float=-1) -> bool:
        return self.l_from == l_from and self.l_to == l_to \
            and (order<0 or self.order == order)

    def is_active(self) -> bool:
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
    
    def to_dict(self) -> dict[str,str|float]:
        result = {
            "from": self.l_from.name,
            "to": self.l_to.name,
            "order": self.order,
            "use": self.use,
            "priority": self.priority
        }
        return result if self.weight < 0 else result | {"weight": self.weight}


def epsilon(value) -> int:
    return (1000 if value%10**6 else 10**6 if value%10**9 else 10**9)

def epsilon2(decimal:str) -> int:
    return 10**abs(int(decimal))

def epsvalue(ev:Optional[ElementValue], values) -> int:
    return Node.epsilon_value * (len(values)+2)

def cvalue(node:Node, vdic) -> float:
    if node.name not in vdic or '円' in vdic[node.name].value:
        return 0.
    return float(vdic[node.name].value)
def cvalue0(node:Node, vdic) -> float:
    if node.name not in vdic or vdic[node.name].value=='NaN' or '円' in vdic[node.name].value:
        return 0.
    return float(vdic[node.name].value)

def subtotal(target, children, vdic) -> list[float]:
    def f(v, target):
        return v.get_weight(target) if v.get_weight(target) is not None else 1.0
    calc_values = [f(v, target) * cvalue(v, vdic) for v in children]
    return [v for v in calc_values if not math.isnan(v)]

def t(name:str) -> str:
    return name.split('_')[-1]

def nmmatch(tagname:str, matcher:list[str]) -> bool:
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
