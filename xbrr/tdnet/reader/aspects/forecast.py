import re
import warnings
from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class Forecast(BaseParser):

    def __init__(self, reader):
        tags = {
            "document_name": "tse-ed-t:DocumentName",
            "security_code": "tse-ed-t:SecuritiesCode",
            "company_name": "tse-ed-t:CompanyName",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",

            "filling_date": "tse-ed-t:FilingDate",
            "forecast_correction_date": "tse-ed-t:ReportingDateOfFinancialForecastCorrection",
            "dividend_correction_date": "tse-ed-t:ReportingDateOfDividendForecastCorrection",

            "forecast_correction_flag": "tse-ed-t:CorrectionOfConsolidatedFinancialForecastInThisQuarter",
            "dividend_correction_flag": "tse-ed-t:CorrectionOfDividendForecastInThisQuarter",

            "sales": "tse-ed-t:Sales",
            "sales_IFRS": "tse-ed-t:SalesIFRS",
            "netsales_IFRS": "tse-ed-t:NetSalesIFRS"
        }
        reit_tags = {
            "document_name": "tse-re-t:DocumentName",
            "security_code": "tse-re-t:SecuritiesCode",
            "company_name": "tse-re-t:IssuerNameREIT",

            "filling_date": "tse-re-t:FilingDate",
            "forecast_correction_date": "tse-ed-t:ReportingDateOfFinancialForecastCorrection",

            "sales_REIT": "tse-re-t:OperatingRevenuesREIT",
            "sales_IFRS": "tse-ed-t:SalesIFRS",
            "netsales_IFRS": "tse-ed-t:NetSalesIFRS"
        }
        if "tse-ed-t" in reader.namespaces:
            super().__init__(reader, ElementValue, tags)
        elif "tse-re-t"in reader.namespaces:
            super().__init__(reader, ElementValue, reit_tags)

        dic = str.maketrans('１２３４５６７８９０（）()［　］〔〕[]','1234567890####% %%%%%')
        title = self.document_name.value.translate(dic).strip().replace(' ','')
        m = re.match(r'(第(.)四半期|中間)?.*決算短信([%#]([^%#]*)[%#])?(#(.*)#)?', title)
        if m != None:
            self.consolidated = '連結' == m.group(6)
            quoater = '2' if m.group(1)is not None and m.group(2) is None else m.group(2)
            self.fiscal_period_kind = 'FY' if m.group(1) is None else 'Q' + quoater
            self.accounting_standards = m.group(4)
        elif ('業績予想' in title or '配当予想' in title):
            self.fiscal_period_kind = '0'
        elif ('剰余金の配当' in title):
            self.fiscal_period_kind = '0'
        elif ('業績' in title):
            self.fiscal_period_kind = '0'
        else:
            raise Exception("Unknown titile found!")

    @property
    def use_IFRS(self):
        return (self.sales_IFRS.value is not None) or (self.netsales_IFRS.value is not None)
    
    @property
    def reporting_date(self):
        wareki = {'令和': 2019}
        dic = str.maketrans('１２３４５６７８９０（）［］','1234567890()[]')
        def wareki2year(elemvalue):
            date1 = elemvalue.value.translate(dic).replace(' ','')
            for waname in wareki.keys():
                m = re.search(r'{}([0-9]+)年'.format(waname), date1.translate(dic).replace(' ',''))
                if m != None:
                    elemvalue.value = date1.replace(
                        waname+m.groups()[0],str(int(m.groups()[0])+wareki[waname]-1))
            return elemvalue

        if self.filling_date.value is not None:
            return wareki2year(self.filling_date)
        if self.forecast_correction_date.value is not None:
            return wareki2year(self.forecast_correction_date)
        if self.dividend_correction_date.value is not None:
            return wareki2year(self.dividend_correction_date)
        raise NameError('Reporting date not found')
    
    @property
    def reporting_period(self):
        role = self.__find_role_name('fc_test')
        if len(role) <= 0: return 'Q2'
        return 'FY'

    @property
    def fc_q2ytd_period(self):
        role = self.__find_role_name('fc_q2ytd')
        if len(role) <= 0: return ''
        return 'Q2'

    @property
    def forecast_year(self):
        return 'NextYear' if self.fiscal_period_kind=='FY' else 'CurrentYear'

    def fc(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('fc')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(fc) if fc is not None else None

    def fc_dividends(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('fc_dividends')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(fc) if fc is not None else None

    def q2ytd(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('fc_q2ytd')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        q2ytd = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(q2ytd) if q2ytd is not None else None

    def __filter_duplicate(self, data):
        # Exclude dimension member
        data.drop_duplicates(subset=("name", "member","period"), keep="first",
                             inplace=True)
        return data

    def __find_role_name(self, finance_statement):
        role_candiates = {
            'fc': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual"], #有価証券報告書,決算短信,業績予想の修正
            'fc_dividends': ["RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"],   #有価証券報告書,決算短信,配当予想の修正
            'fc_test': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual", "RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"],
            'fc_q2ytd': ["InformationQ2YTD"],
        }
        roles = []
        for name in role_candiates[finance_statement]:
            roles += [x for x in self.reader.custom_roles.keys() if name in x and x not in roles]
        return roles
    