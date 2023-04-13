import collections
import importlib
import re
import warnings

if importlib.util.find_spec("pandas") is not None:
    import pandas as pd

from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
            "_fiscal_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI", # 会計期間 from metadata

            "report_FY": "tse-o-di:TypeOfReports-Annual",
            "report_Q1": "tse-o-di:TypeOfReports-FirstQuarter",
            "report_Q2": "tse-o-di:TypeOfReports-SecondQuarter",
            "report_Q3": "tse-o-di:TypeOfReports-ThirdQuarter",
        }

        super().__init__(reader, ElementValue, tags)

    @property
    def use_IFRS(self):
        return self.accounting_standards.value == 'IFRS'

    @property
    def fiscal_period_kind(self):
        if self._fiscal_period_kind.value is not None:
            return self._fiscal_period_kind
        if self.report_Q1.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q1")
        if self.report_Q2.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q2")
        if self.report_Q3.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q3")
        return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="FY")

    def bs(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('bs')
        if len(role) == 0:
            textblock = self.__read_value_by_textblock(["StatementOfFinancialPosition","BalanceSheet"])
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame([{'label':'','value':'','unit':'JPY','context':'','data_type':'','name':'','depth':1}])
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        bs = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(bs)

    def pl(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('pl')
        if len(role) == 0:
            textblock = self.__read_value_by_textblock(["StatementOfIncome", "StatementOfComprehensiveIncome"])
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame([{'label':'','value':'','unit':'JPY','context':'','data_type':'','name':'','depth':1}])
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        pl = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(pl)

    def cf(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('cf')
        if len(role) == 0:
            textblock = self.__read_value_by_textblock(["StatementOfCashFlows"])
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame([{'label':'','value':'','unit':'JPY','context':'','data_type':'','name':'','depth':1}])
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        cf = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(cf)

    def __filter_duplicate(self, data):
        # Exclude dimension member
        if data is not None:
            data.drop_duplicates(subset=("name", "period"), keep="first",
                             inplace=True)
        return data

    def __find_role_name(self, finance_statement):
        role_candiates = {
            'bs': ["StatementOfFinancialPosition", "ConsolidatedBalanceSheet", "BalanceSheet"],
            'pl': ["StatementOfProfitOrLoss", "StatementOfIncome", "ComprehensiveIncomeSingleStatement", "StatementsOfIncome"],
            'cf': ["StatementOfCashFlows"],
        }
        roles = []
        for name in role_candiates[finance_statement]:
            roles += [x for x in self.reader.custom_roles.keys() if name in x and 'Notes' not in x and x not in roles]
        return roles

    def __read_value_by_textblock(self, candidates):
        values = self.reader.find_value_names(candidates)
        textblocks = [x for x in values if x.endswith('TextBlock')]
        if len(textblocks) == 0:
            return None
        element_value = self.reader.findv(textblocks[0])
        return element_value

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
            for record in table.select('tr'):
                columns = list(record.select('td'))
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
