from datetime import datetime

from xbrr.base.reader.base_parser import BaseParser
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue


class Metadata(BaseParser):

    def __init__(self, reader:BaseReader):
        tags = {
            "edinet_code": "jpdei_cor:EDINETCodeDEI",
            "security_code": "jpdei_cor:SecurityCodeDEI",
            "company_name": "jpdei_cor:FilerNameInJapaneseDEI",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI",
            "fiscal_date_start": "jpdei_cor:CurrentFiscalYearStartDateDEI",
            "fiscal_date_end": "jpdei_cor:CurrentFiscalYearEndDateDEI",
            "fiscal_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI",

            "address": "jpcrp_cor:AddressOfRegisteredHeadquarterCoverPage",
            "phone_number": "jpcrp_cor:TelephoneNumberAddressOfRegisteredHeadquarterCoverPage",
        }

        super().__init__(reader, ElementValue, tags)

    @property
    def fiscal_year(self):
        value = self.get_value("fiscal_date_start")
        year = datetime.strptime(value.value, "%Y-%m-%d").year if value else None
        return year

    @property
    def fiscal_year_end_date(self):
        value = self.get_value("fiscal_date_end")
        date = datetime.strptime(value.value, "%Y-%m-%d") if value else None
        return date

    @property
    def fiscal_month(self):
        value = self.get_value("fiscal_date_start")
        month = datetime.strptime(value.value, "%Y-%m-%d").month if value else None
        return month
