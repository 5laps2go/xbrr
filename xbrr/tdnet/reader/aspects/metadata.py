from datetime import datetime

from xbrr.base.reader.base_parser import BaseParser
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue
from xbrr.xbrl.reader.reader import Reader


class Metadata(BaseParser):

    def __init__(self, reader:Reader):
        tags = {
            "edinet_code": "jpdei_cor:EDINETCodeDEI",
            "security_code": "jpdei_cor:SecurityCodeDEI",
            "company_name": "jpdei_cor:FilerNameInJapaneseDEI",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI",
            "fiscal_date_start": "jpdei_cor:CurrentFiscalYearStartDateDEI",
            "fiscal_date_end": "jpdei_cor:CurrentFiscalYearEndDateDEI",
            "_report_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI",

            "address": "jpcrp_cor:AddressOfRegisteredHeadquarterCoverPage",
            "phone_number": "jpcrp_cor:TelephoneNumberAddressOfRegisteredHeadquarterCoverPage",
        }
        tse_o_di_tags = {
            "edinet_code": "tse-o-di:EDINETCode",
            "security_code": "tse-o-di:SecuritiesCode",
            "company_name": "jpfr-di:EntityNameJaEntityInformation",
            # "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI",
            # "fiscal_date_start": "jpdei_cor:CurrentFiscalYearStartDateDEI",
            "fiscal_date_end": "tse-o-di:FiscalYearEnd",
            # "report_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI",
            "_annual": "tse-o-di:TypeOfReports-Annual",
            "_firstquarter": "tse-o-di:TypeOfReports-FirstQuarter",
            "_secondquarter": "tse-o-di:TypeOfReports-SecondQuarter",
            "_thirdquarter": "tse-o-di:TypeOfReports-ThirdQuarter",

            # "address": "jpcrp_cor:AddressOfRegisteredHeadquarterCoverPage",
            # "phone_number": "jpcrp_cor:TelephoneNumberAddressOfRegisteredHeadquarterCoverPage",
        }

        if "jpdei_cor" in reader.namespaces:
            super().__init__(reader, ElementValue, tags)
        elif "tse-o-di"in reader.namespaces:
            super().__init__(reader, ElementValue, tse_o_di_tags)
        else:   # no metadata found
            raise NameError("jpdei_cor or tse-o-di")

    @property
    def fiscal_year(self):
        value = self.get_value("fiscal_date_start")
        year = datetime.strptime(value.value, "%Y-%m-%d").year if value else 1900
        return year

    @property
    def fiscal_year_end_date(self) -> datetime:
        value = self.get_value("fiscal_date_end")
        assert value is not None
        date = datetime.strptime(value.value, "%Y-%m-%d")
        return date

    @property
    def fiscal_month(self):
        value = self.get_value("fiscal_date_start")
        month = datetime.strptime(value.value, "%Y-%m-%d").month if value else None
        return month
    
    @property
    def report_period_kind(self):
        if "_report_period_kind" in self.tags:
            assert self._report_period_kind
            return self._report_period_kind.value
        elif self._annual:
            kind = "FY" if self._annual.value=="true"\
                else "Q1" if self._firstquarter and self._firstquarter.value=="true"\
                else "Q2" if self._secondquarter and self._secondquarter.value=="true"\
                else "Q3"
            return kind
