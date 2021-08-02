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
from xbrr.edinet.reader.element_schema import ElementSchema
from xbrr.edinet.reader.role_schema import RoleSchema
from xbrr.edinet.reader.element_value import ElementValue

class Reader(BaseReader):

    def __init__(self, xbrl_doc: Doc, taxonomy=None, save_dir: str = ""):
        super().__init__("edinet")
        self.xbrl_doc = xbrl_doc
        self.save_dir = save_dir
        self._linkbaseRef = {}
        self._xsd_dic = {}
        self._role_dic = {}
        self._context_dic, self._value_dic, self._namespace_dic =\
            ElementValue.read_xbrl_values(self, self.xbrl)

        if isinstance(taxonomy, Taxonomy):
            self.taxonomy = taxonomy
        else:
            root = Path(self.save_dir).joinpath("external")
            self.taxonomy = Taxonomy(root)
        self.taxonomy_year = ""
        self.__set_taxonomy_year()



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
        if len(self._role_dic) == 0:
            for element in self.xbrl_doc.pre.find_all("link:roleRef"):
                role_name = element["xlink:href"].split("#")[-1]
                self._role_dic[role_name] = RoleSchema.create_role_schema(self, element)
        return self._role_dic

    @property
    def taxonomy_path(self):
        return self.taxonomy.root.joinpath("taxonomy", str(self.taxonomy_year))

    @property
    def namespaces(self):
        return self._namespace_dic

    @property
    def xbrl(self):
        return self.xbrl_doc.xbrl

    def read_by_link(self, link):
        assert "#" in link
        xsduri = link.split("#")[0]
        element = link.split("#")[-1]
        if element not in self._xsd_dic:
            self._xsd_dic.update(ElementSchema.read_schema(self, xsduri))
            # prepare label xml href dict from local xsd
            ElementSchema.read_label_taxonomy(self, xsduri, self._xsd_dic)
        return self._xsd_dic[element]

    def find_role_name(self, financial_statement):
        role_candiates = {
            'bs': [
                "rol_ConsolidatedStatementOfFinancialPositionIFRS" , "rol_BalanceSheet", "rol_ConsolidatedBalanceSheet"
            ],
            'pl': [
                "rol_ConsolidatedStatementOfProfitOrLossIFRS", "rol_StatementOfIncome", "rol_ConsolidatedStatementOfIncome"
            ],
            'cf': [
                "rol_ConsolidatedStatementOfCashFlowsIFRS", "rol_StatementOfCashFlows-indirect", "rol_StatementOfCashFlows-direct",
                "rol_ConsolidatedStatementOfCashFlows-indirect", "rol_ConsolidatedStatementOfCashFlows-direct"
            ],
        }
        for name in role_candiates[financial_statement]:
            if name in self.roles:
                return name
        return None
    
    def find_accounting_standard(self):
        if 'IFRS' in self.find_role_name('bs'):
            return 'IFRS'
        return 'JP'

    def get_role(self, role_name):
        if '/' in role_name:
            role_name = role_name.rsplit('/', 1)[-1]
        return self.roles[role_name]

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

    def read_schema_by_role(self, role_name, use_cal_link=False):
        if not self.xbrl_doc.has_schema:
            raise Exception("XBRL directory is required.")

        nodes = {}
        self.make_node_tree(nodes, role_name, self.xbrl_doc.pre, "link:presentationLink", "link:presentationArc", "parent-child")
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
        for loc in role.find_all("link:loc"):
            locs[loc["xlink:label"]] = loc

        for i, arc in enumerate(role.find_all(arc_node)):
            if not arc["xlink:arcrole"].endswith(arc_role):
                print("Unexpected arctype.")
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


    def read_value_by_role(self, role_link, use_cal_link=False):
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
    
    def read_value_by_textblock(self, accounting_standard, finance_statement):
        textblock_element = {
            'ifrs': {
                'bs': 'jpigp_cor:ConsolidatedStatementOfFinancialPositionIFRSTextBlock',
                'pl': 'jpigp_cor:ConsolidatedStatementOfProfitOrLossIFRSTextBlock',
                'cf': 'jpigp_cor:ConsolidatedStatementOfCashFlowsIFRSTextBlock',
            },
            'sec': {
                'bs': 'jpcrp_cor:ConsolidatedBalanceSheetTextBlock',
                'pl': 'jpcrp_cor:ConsolidatedStatementOfIncomeTextBlock',
                'cf': 'jpcrp_cor:ConsolidatedStatementOfCashFlowsTextBlock',
            },
            'jp': {
                'bs': 'jpcrp_cor:ConsolidatedBalanceSheetTextBlock',
                'pl': 'jpcrp_cor:ConsolidatedStatementOfIncomeTextBlock',
                'cf': 'jpcrp_cor:ConsolidatedStatementOfCashFlowsTextBlock',
            }
        }
        textblock = textblock_element[accounting_standard][finance_statement]
        if accounting_standard == 'ifrs' and 'jpigp_cor' not in self.namespaces:
            textblock = textblock.replace('jpigp_cor:', 'jpcrp_cor:')
        element_value = self.findv(textblock)
        statement_values = ElementValue.read_finance_statement(self, element_value.html)
        return statement_values

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
