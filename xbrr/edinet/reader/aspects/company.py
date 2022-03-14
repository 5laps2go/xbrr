from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class Company(BaseParser):

    def __init__(self, reader):
        tags = {
            "history": "jpcrp_cor:CompanyHistoryTextBlock",
            "business_description": "jpcrp_cor:DescriptionOfBusinessTextBlock",
            "affiliated_entities": "jpcrp_cor:OverviewOfAffiliatedEntitiesTextBlock",
            "employees": "jpcrp_cor:InformationAboutEmployeesTextBlock"
        }
        super().__init__(reader, ElementValue, tags)

