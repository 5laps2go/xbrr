import re
import warnings
from xbrr.base.reader.base_parser import BaseParser
from xbrr.edinet.reader.element_value import ElementValue


class Forecast(BaseParser):

    def __init__(self, reader):
        tags = {
            "document_name": "tse-ed-t:DocumentName",
            "security_code": "tse-ed-t:SecuritiesCode",
            "company_name": "tse-ed-t:CompanyName",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",

            "filling_date": "tse-ed-t:FilingDate",
        }

        super().__init__(reader, ElementValue, tags)

        dic = str.maketrans('１２３４５６７８９０（）［］','1234567890()[]')
        title = self.document_name.value.translate(dic)
        m = re.match(r'(第(.)四半期)?決算短信\〔(.*)\〕\((.*)\)', title)
        if m != None:
            self.consolidated = '連結' == m.groups()[3]
            self.fiscal_period_kind = 'All' if m.groups()[1]==None else 'Q'+m.groups()[1]
            self.accounting_standards = m.groups()[2]

    @property
    def use_IFRS(self):
        if self.find_accounting_standards == 'IFRS':
            return True
        else:
            return False

    def fc(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('fc')
        assert len(role) > 0
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        if fc is None:
            return None
        else:
            return self.__filter_duplicate(fc)

    def __filter_duplicate(self, data):
        # Exclude dimension member
        data.drop_duplicates(subset=("name", "period"), keep="first",
                             inplace=True)
        return data

    def __find_role_name(self, finance_statement):
        role_candiates = {
            'fc': ["RoleForecasts", "Forecasts"],
        }
        roles = []
        for name in role_candiates[finance_statement]:
            roles += [x for x in self.reader.custom_roles.keys() if name in x and x not in roles]
        return roles
    