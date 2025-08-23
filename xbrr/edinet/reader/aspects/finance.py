from typing import Optional, Literal, Callable, cast

from datetime import date, datetime
import collections
import importlib
import importlib.util
import re
import warnings
import pandas as pd

if importlib.util.find_spec("pandas") is not None:
    import pandas as pd

from xbrr.base.reader.base_parser import BaseParser
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader:BaseReader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
            "report_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI", # 会計期間 from metadata
        }

        super().__init__(reader, ElementValue, tags)

    @property
    def consolidated(self):
        cons_noncons = set([x['cons_nocons'] for x in self.reader.role_decision_info if 'table' in x])
        if 'NonConsolidatedMember' in cons_noncons and all([x not in cons_noncons for x in ['ConsolidatedMember','ConsNonconsMember']]):
            return False
        return True

    @property
    def fiscal_period_end_date(self) -> date:
        raise NotImplementedError("You have to implement fiscal_period_end_date.")

    def bs(self, latest2year=False):
        role_uri = self.find_role_name('bs')
        if not role_uri:
            textblock = self.read_value_by_textblock('bs')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        bs = self.reader.read_value_by_role(role_uri)
        return self.latest2year(bs, latest2year)

    def pl(self, latest2year=False):
        role_uri = self.find_role_name('pl')
        if not role_uri:
            textblock = self.read_value_by_textblock('pl')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        pl = self.reader.read_value_by_role(role_uri)
        return self.latest2year(pl, latest2year)

    def cf(self, latest2year=False):
        role_uri = self.find_role_name('cf')
        if not role_uri:
            textblock = self.read_value_by_textblock('cf')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        cf = self.reader.read_value_by_role(role_uri)
        return self.latest2year(cf, latest2year)
    
    def latest2year(self, df:pd.DataFrame, latest2year:bool):
        if latest2year:
            no_quarter = '~context.str.contains("Quarter")|~context.str.contains("Duration")'  # eliminate QuarterDuration, not QuarterInstance
            df = df.query(no_quarter, engine='python')
        return df

    def find_role_name(self, finance_type:Literal['bs','pl','cf']) -> Optional[str]:
        scanstable = [x for x in self.reader.role_decision_info if 'table' in x]
        # old style presentation before 2014
        if all([x['table']=='' for x in scanstable]):
            return self.find_role_name2013(scanstable, finance_type)
        # current style presentation after 20140116
        assert any([x['table']!='' for x in scanstable])
        return self.find_role_nameXXXX(scanstable, finance_type)

    def find_role_nameXXXX(self, scans:list[BaseReader.PreTable], finance_type:Literal['bs','pl','cf']) -> Optional[str]:
        table_candidates = {
            'bs': ['BalanceSheetTable','StatementOfFinancialPositionIFRSTable'],
            'pl': ['StatementOfIncomeTable','StatementOfProfitOrLossIFRSTable','StatementOfComprehensiveIncomeIFRSTable'],  # StatementOfProfitOrLossIFRSTable from 2019-04-23, StatementOfComprehensiveIncomeIFRSTable without ProfitOrLossIFRSTable from 2019-04-25
            'cf': ['StatementOfCashFlowsTable','StatementOfCashFlowsIFRSTable'],
            'che': ['StatementOfChangesInEquityTable','StatementOfChangesInEquityIFRSTable'],
        }
        for table in table_candidates[finance_type]:
            for scan in scans:
                if table == scan['table'] and self.consolidated == (scan['cons_nocons']=="ConsolidatedMember"):
                    return scan['xlink_role']
        # オリックス株式会社【8591】 is 〔米国基準〕(連結), but only NonConsolidated financial report(XBRL) and Consolidated financial TextBlock
        # # for table in table_candidates[finance_type]:
        # #     for scan in scans: if table == scan['table']: return scan['xlink_role']
        return None

    def find_role_name2013(self, scans:list[BaseReader.PreTable], finance_type:Literal['bs','pl','cf']) -> Optional[str]:
        table_candidates2013 = {
            'bs': ['BalanceSheets'],
            'pl': ['StatementsOfIncome'],
            'cf': ['StatementsOfCashFlows'],
            'cha': ['StatementsOfChangesInNetAssets'],
        }
        for table in table_candidates2013[finance_type]:
            for scan in scans:
                if table in scan['xlink_role'] and \
                    (not self.consolidated) == ('NonConsolidated' in scan['xlink_role'].split(table)[0]):   # ConsolidatedXXX, ConsolidatedQuarterlyXXX
                    return scan['xlink_role']
        return None

    def read_value_by_textblock(self, finance_type:Literal['bs','pl','cf']) -> Optional[ElementValue]:
        textblock_candidates = {
            'bs': ['BalanceSheetHeading'], #,'StatementOfFinancialPositionIFRSHeading']) # 
            'pl': ['StatementOfIncomeHeading','StatementOfProfitOrLossIFRSHeading','StatementOfComprehensiveIncomeSingleStatementHeading'], # StatementOfComprehensiveIncomeSingleStatementHeading:6464:2018-02-14
            'cf': ['StatementOfCashFlowsHeading','StatementOfCashFlowsIFRSHeading'],
        }
        scansheading = [x for x in self.reader.role_decision_info if 'heading' in x]
        for heading in textblock_candidates[finance_type]:
            for scan in scansheading:
                if heading in scan['heading'] and \
                   self.consolidated == (scan['cons_nocons']=='Consolidated'):
                    textblock_name = ':'.join(scan['xlink_href'].split('_', 2))
                    textblock = self.reader.findv(textblock_name)
                    return textblock
        return None

    def __read_finance_statement(self, statement_xml):
        def myen(vtext, unit):
            if vtext in ['－', '-', '―'] or len(vtext)==0:
                return ''
            myen = vtext.replace(',','').replace('△', '-') + unit
            return myen
        def isnum(myen):
            try:
                float(myen)
            except ValueError:
                return False
            else:
                return True
        def label_margin(columns):
            label = ''.join([x.text.strip() for x in columns[0].select('p')])
            if label != '' and columns[0].get('colspan',"") == '': # column0 has label
                style_str = columns[0].find('p').get('style',"") if label != "" else ""
                m = re.match(r'.*-left: *([0-9]*).?[0-9]*p[tx].*', style_str)
                margin = m.groups()[0] if m is not None else "0"
            else: # columns construct the label structure
                margin = 0
                for margin in range(0,len(columns)+prevcol):
                    label = ''.join([x.text.strip() for x in columns[margin].select('p')])
                    if label!='': break
            return (label, margin)
        def get_value(column):
            text = column.text.strip()
            tokens = re.split('[ \xa0\n]', text)
            value = myen(tokens[-1], unit)
            return value if isnum(value) or value=='' else text
        indent_state = []
        def indent_label(margin_left):
            delidx = [i for i,x in enumerate(indent_state) if int(x) > int(margin_left)]
            if len(delidx) > 0: del indent_state[delidx[0]:]
            indent_state.append(margin_left)
            c = collections.Counter(indent_state)
            ks = sorted(c.keys(), key=int)
            return "-".join([str(c[x]) for x in ks])

        thiscol, prevcol = -1, -2
        unit = '000000'
        values = []
        for table in statement_xml.select('table'):
            if table.find_parents('table'): continue
            tbody = _tbody if (_tbody:=table.find('tbody', recursive=False)) else table
            for record in tbody.find_all('tr', recursive=False):
                columns = list(record.find_all('td', recursive=False))
                label, margin = label_margin(columns)
                value = get_value(columns[thiscol])

                if label != "" and value == "": # skip headding part
                    # label+"合計"でここから始まるブロックが終わるという規約であれば、depthに依存関係を入れられる
                    indent = indent_label(margin)
                elif isnum(value):
                    if '.' in value or label == '': continue   # skip float value １株当たり四半期利益
                    prev_value = get_value(columns[prevcol])
                    indent = indent_label(margin)
                    depth = len(indent.split('-'))
                    if isnum(prev_value):
                        values.append({
                            'label': label,
                            'value': prev_value,
                            'unit': 'JPY',
                            'indent': indent,
                            'context': 'Prior1YTDDuration',
                            'data_type': 'monetary',
                            'name': "dummy",
                            'depth': depth
                        })
                    values.append({
                        'label': label,
                        'value': value,
                        'unit': 'JPY',
                        'indent': indent,
                        'context': 'CurrentYTDDuration',
                        'data_type': 'monetary',
                        'name': "dummy",
                        'depth': depth
                    })
                else:
                    assert label=='' or value=='' or  '円' in value or any([x.text.strip().startswith('当') for x in columns]) #'当連結会計年度' in value
                    if '百万円' in value: # 単位：百万円 金額（百万円）
                        unit = '000000'
                    elif '千円' in value:
                        unit = '000'
                    elif '単位：円' in value or '円' in value:
                        unit = ''
                    # if value.startswith('当'): #'当連結会計年度' in value
                    if any([x.text.strip().startswith('当') for x in columns]): #'当連結会計年度' in value
                        collen = sum([int(c.get('colspan','1')) for c in columns])
                        idx = 0
                        for c in columns:
                            if c.text.strip().startswith('前'):
                                prevcol = idx - collen
                            elif c.text.strip().startswith('当'):
                                thiscol = idx - collen
                            idx = idx + int(c.get('colspan','1'))
        return pd.DataFrame(values)
