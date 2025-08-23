from typing import Optional, Literal, Callable, cast

from datetime import date, datetime, timedelta
import calendar
import collections
import importlib
import importlib.util
import itertools
import re
import warnings
from bs4 import BeautifulSoup
import pandas as pd
from logging import getLogger

from pandas import DataFrame

if importlib.util.find_spec("pandas") is not None:
    import pandas as pd

from xbrr.base.reader.base_parser import BaseParser
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
            "_report_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI", # 会計期間 from metadata
            "_fiscal_year_start_date": "jpdei_cor:CurrentFiscalYearStartDateDEI",
            "_fiscal_year_end_date": "jpdei_cor:CurrentFiscalYearEndDateDEI",
            "company_name": "jpdei_cor:FilerNameInJapaneseDEI",

            "_fiscal_year_end_date0": "tse-o-di:FiscalYearEnd",
            "report_FY": "tse-o-di:TypeOfReports-Annual",
            "report_Q1": "tse-o-di:TypeOfReports-FirstQuarter",
            "report_Q2": "tse-o-di:TypeOfReports-SecondQuarter",
            "report_Q3": "tse-o-di:TypeOfReports-ThirdQuarter",

            # old style xbrl
            # "consolidated_flag": "jpfr-di:ConsolidatedBSConsolidatedFinancialStatements",
            # new style xbrl
            "whether_consolidated": "jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI",
        }

        self._YTD_role_piece = ["YearToQuarterEnd", "IncomeYTD"] # 四半期累計期間
        self._Quarter_period_role_piece = ["QuarterPeriod", "IncomeQuater"] # 四半期会計期間

        super().__init__(reader, ElementValue, tags)

    def get_security_code(self):
        return self.reader.xbrl_doc.company_code

    def get_company_name(self) -> str:
        value = self.get_value("company_name")
        return value.value if value else 'not found'

    @property
    def fiscal_year_start_date(self) -> date:
        value = self.get_value("_fiscal_year_start_date")
        if value is not None:
            return datetime.strptime(value.value, "%Y-%m-%d").date()
        else:  # backward compatibility for old style xbrl
            end_date = self.fiscal_year_end_date
            assert end_date != None
            start_date = end_date - timedelta(days=364)
            return date(year=start_date.year, month=start_date.month, day=1)

    @property
    def fiscal_year_end_date(self) -> date:
        value = self.get_value("_fiscal_year_end_date")
        if value is not None:
            return datetime.strptime(value.value, "%Y-%m-%d").date()
        else:  # backward compatibility for old style xbrl
            value = self.get_value("_fiscal_year_end_date0")
            return datetime.strptime(value.value, "%Y-%m-%d").date() if value else date(year=9999, month=12, day=31)

    @property
    def report_period_end_date(self) -> date:
        return self.reader.xbrl_doc.report_period_end_date

    @property
    def reporting_iso_date(self) -> str:
        return self.reader.xbrl_doc.published_date[0].date().isoformat()

    @property
    def report_period_kind(self) -> ElementValue:
        if self._report_period_kind is not None:
            return self._report_period_kind
        if self.report_Q1 and self.report_Q1.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q1")
        if self.report_Q2 and self.report_Q2.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q2")
        if self.report_Q3 and self.report_Q3.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q3")
        return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="FY")

    @property
    def consolidated(self) -> bool:
        return self.reader.xbrl_doc.consolidated

    def bs(self, latest2year=False) -> DataFrame:
        role_uri = self.find_role_name('bs')
        if not role_uri:
            textblock = self.read_value_by_textblock('bs')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        bs = self.reader.read_value_by_role(role_uri, report_start=self.fiscal_year_start_date, report_end=self.report_period_end_date)
        return self.latest2year(bs, latest2year)

    def pl(self, latest2year=False) -> DataFrame:
        fix_cal = ['GrossProfit','GrossProfitNetGP','OperatingGrossProfit','GrossProfitIFRS',  # '~^GrossProfit.{,5}$', 1848:2011-05-11 fail, 
                   'OperatingIncome', 'OperatingProfitLossIFRS','<OperatingIncome','~(?<!Non)(?<!Other)OperatingIncome','NormalizedOperatingProfitIFRS',
                   'OrdinaryIncome','OrdinaryIncomeBNK','>OrdinaryProfitLoss','~(Operating|Ordinary)[Ll]oss$',
                   'ProfitLossBeforeTax','ProfitLossBeforeTaxIFRS',  # 2282:2022-05-10
                   'BusinessProfitLossIFRS','BusinessProfitPLIFRS','~Profit$'] # BusinessProfitPLIFRS 7951:2019-08-01, ~[Ll]oss$: 6084:2014-08-14

        role_uri = self.find_role_name('pl', exclusion=self._Quarter_period_role_piece)
        if not role_uri:
            textblock = self.read_value_by_textblock('pl')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        pl = self.reader.read_value_by_role(role_uri, fix_cal_node=fix_cal, report_start=self.fiscal_year_start_date, report_end=self.report_period_end_date)
        return self.latest2year(pl, latest2year)

    def cf(self, latest2year=False) -> DataFrame:
        role_uri = self.find_role_name('cf')
        if not role_uri:
            textblock = self.read_value_by_textblock('cf')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        cf = self.reader.read_value_by_role(role_uri, report_start=self.fiscal_year_start_date, report_end=self.report_period_end_date)
        return self.latest2year(cf, latest2year)

    def latest2year(self, df:DataFrame, latest2year:bool) -> DataFrame:
        if latest2year and 'context' in df.columns:
            no_quarter = '~context.str.contains("Quarter")|~context.str.contains("Duration")'  # eliminate QuarterDuration, not QuarterInstance
            df = df.query(no_quarter, engine='python')
        return df if not df.empty else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

    def scan_presentation(self) -> list[BaseReader.PreTable|BaseReader.PreHeading]:
        return self.reader.role_decision_info

    def find_role_name(self, finance_type:Literal['bs','pl','cf'], exclusion:list[str]=[]) -> Optional[str]:
        scanstable = [x for x in self.scan_presentation() if 'table' in x]
        # old style presentation before 2014
        if all([x['table']=='' for x in scanstable]):
            return self.find_role_name2013(scanstable, finance_type)
        # current style presentation after 20140116
        assert any([x['table']!='' for x in scanstable])
        return self.find_role_nameXXXX(scanstable, finance_type, exclusion)

    def find_role_nameXXXX(self, scans:list[BaseReader.PreTable], finance_type:Literal['bs','pl','cf'], exclusion:list[str]) -> Optional[str]:
        table_candidates = {
            'jp': {  # Japanese GAAP
                'bs': ['BalanceSheetTable'],
                'pl': ['StatementOfIncomeTable'],
                'cf': ['StatementOfCashFlowsTable'],
                'che': ['StatementOfChangesInEquityTable'],

            },
            'if': {  # IFRS
                'bs': ['StatementOfFinancialPositionIFRSTable'],
                'pl': ['StatementOfProfitOrLossIFRSTable', 'StatementOfComprehensiveIncomeIFRSTable'],  # StatementOfProfitOrLossIFRSTable from 2019-04-23, StatementOfComprehensiveIncomeIFRSTable without ProfitOrLossIFRSTable from 2019-04-25
                'cf': ['StatementOfCashFlowsIFRSTable'],
                'che': ['StatementOfChangesInEquityTable', 'StatementOfChangesInEquityIFRSTable'],
            },
            'us': {  # US GAAP
                'bs': ['BalanceSheetTable'],
                'pl': ['StatementOfIncomeTable'],
                'cf': ['StatementOfCashFlowsTable'],
                'che': ['StatementOfChangesInEquityTable'],
            }
        }
        accounting_standards = self.reader.xbrl_doc.accounting_standard
        for table in table_candidates[accounting_standards][finance_type]:
            for scan in scans:
                if table == scan['table'] and self.consolidated == (scan['cons_nocons']=="ConsolidatedMember"):
                    if any([ex in scan['xlink_role'] for ex in exclusion]):
                        continue
                    return scan['xlink_role']
        return None

    def find_role_name2013(self, scans:list[BaseReader.PreTable], finance_type:Literal['bs','pl','cf']) -> Optional[str]:
        table_candidates2013 = {
            'bs': ['BalanceSheets'],
            'pl': ['StatementsOfIncomeYTD','StatementsOfIncome'],
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
                if heading == scan['heading'] and \
                   self.consolidated == (scan['cons_nocons']=='Consolidated'):
                    textblock_name = ':'.join(scan['xlink_href'].split('_', 2))
                    textblock = self.reader.findv(textblock_name)
                    return textblock
        return None

    def __read_finance_statement(self, statement_xml):
        def myen(vtext, unit):
            if vtext in ['－', '-', '―'] or len(vtext)==0:
                return ''
            myen = vtext.translate(str.maketrans({',':None, '△':'-', '(': None, ')':None})) + unit
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
            return (label.replace(' ','').replace('\u3000',''), margin)
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
        def analyze_title(columns, thiscol, prevcol, this_str, prev_str):
            def col_year(c):
                years = [int(x) for x in re.split(r'[^\d]',c.text) if x!='' and int(x)>1900]
                if c.text.strip().startswith('前') and '増減' not in c.text:
                    return 1
                elif c.text.strip().startswith('当'):
                    return 9999
                elif years:
                    return years[0]
                return -1
            colindex = list(itertools.accumulate([int(c.get('colspan','1')) for c in columns]))
            year_index = sorted([(col_year(c),colindex[i-1]-colindex[-1]) for i,c in enumerate(columns) if col_year(c)>0], key=lambda x: x[1])
            if len(year_index) > 0: thiscol = year_index[0][1]
            if len(year_index) > 1:
                prevcol = year_index[1][1]
                if year_index[0][0] < year_index[1][0]: thiscol, prevcol = prevcol, thiscol
            return thiscol, prevcol
        def analyze_column(label, columns, tc, pc):
            def adjust(columns, idx):
                for i in range(3):
                    if columns[idx+i].text.strip().replace(',','').isdigit():
                        return i
                return 0
            if len(label) > 2 and not any([c in label for c in '([/#,.])']):
                return tc + adjust(columns, tc), pc + adjust(columns, pc)
            return tc, pc

        thiscol, prevcol = -1, -2
        unit = '000000'
        values = []
        for table in statement_xml.select('table'):
            if (thead := table.find('thead', recursive=False)):
                for record in thead.find_all('tr', recursive=False):
                    columns = list(record.find_all('td', recursive=False))
                    if len(values)==0:
                        this_str = str(self.report_period_end_date.year)
                        prev_str = str(int(this_str)-1)
                        thiscol, prevcol = analyze_title(columns, thiscol, prevcol, this_str, prev_str)
            tbody = _tbody if (_tbody:=table.find('tbody', recursive=False)) else table
            for record in tbody.find_all('tr', recursive=False):
                columns = list(record.find_all('td', recursive=False))
                if len(columns) < max(abs(thiscol), abs(prevcol))+1: continue
                label, margin = label_margin(columns)
                if len(values)==0: thiscol,prevcol = analyze_column(label, columns, thiscol, prevcol)
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
                        prioryear = self.report_period_end_date.year - 1
                        values.append({
                            'label': label,
                            'value': prev_value,
                            'unit': 'JPY',
                            'indent': indent,
                            'context': 'Prior1YTDDuration',
                            'data_type': 'monetary',
                            'name': "dummy",
                            'depth': str(depth),
                            'consolidated': True,
                            'period': date(year=prioryear, month=self.report_period_end_date.month,
                                            day=calendar.monthrange(prioryear, self.report_period_end_date.month)[1]).strftime("%Y-%m-%d")
                        })
                    values.append({
                        'label': label,
                        'value': value,
                        'unit': 'JPY',
                        'indent': indent,
                        'context': 'CurrentYTDDuration',
                        'data_type': 'monetary',
                        'name': "dummy",
                        'depth': str(depth),
                        'consolidated': True,
                        'period': self.report_period_end_date.strftime("%Y-%m-%d")
                    })
                else:
                    # assert label=='' or value=='' or any(['円' in x.text for x in columns]) or any([x.text.strip().startswith('当') for x in columns]) #'当連結会計年度' in value
                    if any(['百万円' in x.text for x in columns]): # 単位：百万円 金額（百万円）
                        unit = '000000'
                    elif any(['千円' in x.text for x in columns]):
                        unit = '000'
                    elif any(['円' in x.text for x in columns]):
                        unit = ''
                    # if value.startswith('当'): #'当連結会計年度' in value
                    if len(values)==0:
                        this_str = str(self.report_period_end_date.year)
                        prev_str = str(int(this_str)-1)
                        thiscol, prevcol = analyze_title(columns, thiscol, prevcol, this_str, prev_str)
        headers = ['label','value','unit','indent','context','data_type','name','depth','consolidated','period']
        return pd.DataFrame(values, columns=headers).drop_duplicates(subset=['label', 'context'], keep='first')
