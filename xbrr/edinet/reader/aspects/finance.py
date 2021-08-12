import warnings
import re
import importlib
if importlib.util.find_spec("pandas") is not None:
    import pandas as pd
from xbrr.base.reader.base_parser import BaseParser
from xbrr.edinet.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
        }

        super().__init__(reader, ElementValue, tags)

    @property
    def use_IFRS(self):
        if self.find_accounting_standards.value == 'IFRS':
            return True
        else:
            return False

    def bs(self, ifrs=False, use_cal_link=True):
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet"
        if ifrs and self.use_IFRS:
            role_uri = "http://disclosure.edinet-fsa.go.jp/role/jpigp/rol_ConsolidatedStatementOfFinancialPositionIFRS"

        bs = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(bs)

    def pl(self, ifrs=False, use_cal_link=True):
        role_uri = "http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_StatementOfIncome"
        if ifrs and self.use_IFRS:
            role_base = "http://disclosure.edinet-fsa.go.jp/role/jpigp/"
            role_uri = f"{role_base}rol_ConsolidatedStatementOfComprehensiveIncomeIFRS"

        pl = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(pl)

    def cf(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('cf')
        if len(role) == 0:
            textblock = self.__read_value_by_textblock(["StatementOfCashFlows"])
            return self.__read_finance_statement(textblock.html)
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
            'bs': ["StatementOfFinancialPositionIFRS", "BalanceSheet"],
            'pl': ["StatementOfProfitOrLossIFRS", "StatementOfIncome"],
            'cf': ["StatementOfCashFlowsIFRS", "StatementOfCashFlows"],
        }
        for name in role_candiates[finance_statement]:
            roles = [x for x in self.reader.custom_roles.keys() if name in x and 'Notes' not in x]
        return roles

    def __read_value_by_textblock(self, candidates):
        values = self.reader.find_value_names(candidates)
        textblocks = [x for x in values if x.endswith('TextBlock')]
        if len(textblocks) == 0:
            return None
        element_value = self.reader.findv(textblocks[0])
        return element_value

    def __read_finance_statement(self, statement_xml):
        def myen(value):
            if value=='－':
                return '000'
            myen = value.replace(',','').replace('△', '-')
            return myen
        def isnum(myen):
            try:
                float(myen)
            except ValueError:
                return False
            else:
                return True

        unit = ''
        values = []
        for table in statement_xml.select('table'):
            for record in table.select('tr'):
                columns = list(record.select('td'))
                label = columns[0].text.strip()
                value = myen(columns[-1].text.strip())
                style_str = columns[0].find('p')['style'] if label != "" else ""
                m = re.match(r'.*margin-left: *([0-9]*)px.*', style_str)

                if isnum(value):
                    values.append({
                        'label': label,
                        'value': value + unit,
                        'indent': m.groups()[0]
                    })
                elif label != "" and value == "":
                    values.append({
                        'label': label,
                        'indent': m.groups()[0]
                    })
                else:
                    assert value=='' or '単位：' in value or '百万円' in value or '当連結会計年度' in value
                    if '百万円' in value: # 単位：百万円 金額（百万円）
                        unit = '000000'
                    elif '単位：円' in value:
                        unit = ''
        return pd.DataFrame(values)
