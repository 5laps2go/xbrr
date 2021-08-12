import warnings
from xbrr.base.reader.base_parser import BaseParser
from xbrr.edinet.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
            "fiscal_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI", # 会計期間 from metadata
        }

        super().__init__(reader, ElementValue, tags)

    @property
    def use_IFRS(self):
        if self.find_accounting_standards.value == 'IFRS':
            return True
        else:
            return False

    def bs(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('bs')[0]
        role_uri = self.reader.get_role(role).uri

        bs = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        if bs is None:
            return None
        else:
            return self.__filter_duplicate(bs)

    def pl(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('pl')[0]
        role_uri = self.reader.get_role(role).uri

        pl = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        if pl is None:
            return None
        else:
            return self.__filter_duplicate(pl)

    def cf(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('cf')
        if len(role) == 0:
            return None

        role = role[0]
        role_uri = self.reader.get_role(role).uri

        cf = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        if cf is None:
            return None
        else:
            return self.__filter_duplicate(cf)

    def __filter_duplicate(self, data):
        # Exclude dimension member
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
            roles = [x for x in self.reader.custom_roles.keys() if name in x]
        print(roles)
        return roles
