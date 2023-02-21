import re
import warnings
from datetime import datetime

from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class Forecast(BaseParser):
    tse_ed_t_role_candiates = {
        'fc': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual"], #有価証券報告書,決算短信,業績予想の修正
        'fc_dividends': ["RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"],   #有価証券報告書,決算短信,配当予想の修正
        'fc_test': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual", "RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"]+["EntityInformation"], # EntityInformation for 2013 sm
        'fc_q2ytd': ["InformationQ2YTD"],
    }
    tse_t_ed_role_candiates = {
        'fc': ["Consolidated"], #有価証券報告書,決算短信,業績予想の修正
        'fc_dividends': [],   #有価証券報告書,決算短信,配当予想の修正
        'fc_test': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual", "RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"]+["EntityInformation"], # EntityInformation for 2013 sm
    }


    def __init__(self, reader):
        tags = {
            "document_name": "tse-ed-t:DocumentName",
            "security_code": "tse-ed-t:SecuritiesCode",
            "company_name": "tse-ed-t:CompanyName",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",

            "fiscal_date_end": "tse-ed-t:FiscalYearEnd",
            "filling_date": "tse-ed-t:FilingDate",
            "forecast_correction_date": "tse-ed-t:ReportingDateOfFinancialForecastCorrection",
            "dividend_correction_date": "tse-ed-t:ReportingDateOfDividendForecastCorrection",

            "forecast_correction_flag": "tse-ed-t:CorrectionOfConsolidatedFinancialForecastInThisQuarter",
            "dividend_correction_flag": "tse-ed-t:CorrectionOfDividendForecastInThisQuarter",

            "sales": "tse-ed-t:Sales",
            "sales_IFRS": "tse-ed-t:SalesIFRS",
            "netsales_IFRS": "tse-ed-t:NetSalesIFRS",
            "profit_IFRS": "tse-ed-t:ProfitIFRS"
        }
        tse_t_ed_tags = {
            "document_name": "tse-t-ed:DocumentName",
            "security_code": "tse-t-ed:SecuritiesCode",
            "company_name": "tse-t-ed:CompanyName",
            "company_name_en": "jpdei_cor:FilerNameInEnglishDEI",

            "fiscal_date_end": "tse-t-ed:FiscalYearEnd",
            "filling_date": "tse-t-ed:FilingDate",
            "forecast_correction_date": "tse-t-rv:ReportingDateOfFinancialForecastCorrection",
            "dividend_correction_date": "tse-t-rv:ReportingDateOfDividendForecastCorrection",

            "forecast_correction_flag": "tse-t-ed:CorrectionOfConsolidatedFinancialForecastInThisQuarter",
            "dividend_correction_flag": "tse-t-ed:CorrectionOfDividendForecastInThisQuarter",

            "sales": "tse-t-ed:Sales",
            "sales_IFRS": "tse-t-ed:SalesIFRS",
            "netsales_IFRS": "tse-t-ed:NetSalesIFRS",
            "profit_IFRS": "tse-t-ed:ProfitIFRS",

            "ForecastDividendPerShare": "tse-t-ed:ForecastDividendPerShareAnnual",
            "ForecastDividendPerShareUpper":"tse-t-ed:ForecastUpperDividendPerShareAnnual",
            "ForecastDividendPerShareLower":"tse-t-ed:ForecastLowerDividendPerShareAnnual",
        }
        reit_tags = {
            "document_name": "tse-re-t:DocumentName",
            "security_code": "tse-re-t:SecuritiesCode",
            "company_name": "tse-re-t:IssuerNameREIT",

            "filling_date": "tse-re-t:FilingDate",
            "forecast_correction_date": "tse-ed-t:ReportingDateOfFinancialForecastCorrection",

            "sales_REIT": "tse-re-t:OperatingRevenuesREIT",
            "sales_IFRS": "tse-ed-t:SalesIFRS",
            "netsales_IFRS": "tse-ed-t:NetSalesIFRS",
            "profit_IFRS": "tse-ed-t:ProfitIFRS"
        }
        if "tse-ed-t" in reader.namespaces:
            super().__init__(reader, ElementValue, tags)
            self.namespace_prefix = 'tse-ed-t'
            self.role_candidates = self.tse_ed_t_role_candiates
        elif "tse-re-t"in reader.namespaces:
            super().__init__(reader, ElementValue, reit_tags)
            self.namespace_prefix = 'tse-re-t'
            self.role_candidates = self.tse_ed_t_role_candiates
        elif "tse-t-ed" in reader.namespaces:
            super().__init__(reader, ElementValue, tse_t_ed_tags)    # for old tdnet
            self.namespace_prefix = 'tse-t-ed'
            self.role_candidates = self.tse_t_ed_role_candiates

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
        return (self.profit_IFRS.value is not None) or \
            (self.netsales_IFRS.value is not None) or (self.sales_IFRS.value is not None)
    
    @property
    def reporting_date(self):
        wareki = {'令和': 2019, '平成': 1989, '昭和': 1926}
        def wareki2year(elemvalue):
            date1 = elemvalue.value.replace(' ','')
            for waname in wareki.keys():
                m = re.search(r'{}([0-9]+)年'.format(waname), date1)
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
    def fiscal_year_end_date(self):
        value = self.get_value("fiscal_date_end")
        date = datetime.strptime(value.value, "%Y-%m-%d") if value.value else None
        return ElementValue('fiscal_year_end_date', value=date)

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

        fc = self.reader.read_value_by_role(role_uri, use_cal_link=False)
        if self.namespace_prefix=='tse-t-ed':
            pre_ver = self.reader.schema_tree.presentation_version()
            if pre_ver in ['2012-03-31', '2012-06-30']:
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_0_label': 'label'})
            else:
                assert pre_ver in ['2007-06-30', '2010-03-31', '2011-06-30']
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_2_label': 'label'})
        return self.__filter_duplicate(fc) if fc is not None else None

    def fc_dividends(self, ifrs=False, use_cal_link=True):
        role = self.__find_role_name('fc_dividends')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri, use_cal_link=use_cal_link)
        return self.__filter_duplicate(fc) if fc is not None else None
    
    def dividend_per_share(self) -> float:
        import numpy as np
        if self.namespace_prefix=='tse-t-ed':
            try:
                if self.ForecastDividendPerShare.value is not None:
                    return float(self.ForecastDividendPerShare.value)
                if self.ForecastUpperDividendPerShare.value is not None:
                    upper = float(self.ForecastUpperDividendPerShare.value)
                    lower = float(self.ForecastLowerDividendPerShare.value)
                    return (upper + lower)/2
            except ValueError:
                pass
            return np.nan
        fc_df = self.fc_dividends()
        if fc_df is None:
            return np.nan
        query_forecast_figures = 'value!=""&context.str.contains("{}")&not member.str.contains("Previous")&not member.str.startswith("Annual")'.format(self.forecast_year)
        fc_df = fc_df.query(query_forecast_figures, engine='python')
        money = fc_df.query('data_type=="perShare"')[['name','value']].astype({'value':float})
        return money.query('name=="tse-ed-t:DividendPerShare"')['value'].sum()

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
        custom_roles_dic = self.reader.custom_roles
        roles = []
        for name in self.role_candidates[finance_statement]:
            roles += [x for x in custom_roles_dic.keys() if name in x and x not in roles]
        return roles
    