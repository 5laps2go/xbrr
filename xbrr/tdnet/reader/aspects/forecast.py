from typing import Literal, Optional

import re
import warnings
from datetime import date, datetime
from pandas import DataFrame

from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.reader import Reader
from xbrr.xbrl.reader.element_value import ElementValue


class Forecast(BaseParser):
    tse_ed_t_role_candiates = {
        'fc': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual"], #有価証券報告書,決算短信,業績予想の修正
        'fc_dividends': ["RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"],   #有価証券報告書,決算短信,配当予想の修正
        'fc_test': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual", "RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"]+["EntityInformation"], # EntityInformation for 2013 sm
        'fc_q2ytd': ["InformationQ2YTD"],
    }
    tse_t_ed_role_candiates: dict[str, list[str]] = {
        'fc': ["Consolidated"], #有価証券報告書,決算短信,業績予想の修正
        'fc_dividends': [],   #有価証券報告書,決算短信,配当予想の修正
        'fc_test': ["RoleForecasts", "RoleQuarterlyForecasts", "InformationAnnual", "RoleDividends", "RoleQuarterlyDividends", "RoleRevisedDividend"]+["EntityInformation"], # EntityInformation for 2013 sm
    }


    def __init__(self, reader:Reader):
        def gen_fiscal_period_kind(m:re.Match[str]) -> str:
            quoater = '2' if m.group(1)is not None and m.group(2) is None else m.group(2)
            return 'Q'+quoater if quoater is not None else '0'
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

            "ForecastDividendPerShare": "tse-t-ed:ForecastDividendPerShareAnnual",
            "ForecastUpperDividendPerShare":"tse-t-ed:ForecastUpperDividendPerShareAnnual",
            "ForecastLowerDividendPerShare":"tse-t-ed:ForecastLowerDividendPerShareAnnual",
        }
        reit_tags = {
            "document_name": "tse-re-t:DocumentName",
            "security_code": "tse-re-t:SecuritiesCode",
            "company_name": "tse-re-t:IssuerNameREIT",

            "filling_date": "tse-re-t:FilingDate",
            "forecast_correction_date": "tse-ed-t:ReportingDateOfFinancialForecastCorrection",
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

        if self.document_name is None:
            raise Exception("Unknown titile found!")

        dic = str.maketrans('１２３４５６７８９０（）()［　］〔〕[]','1234567890####% %%%%%')
        title = self.document_name.value.translate(dic).strip().replace(' ','')
        m = re.search(r'(第(.)四半期|中間)?.*決算短信([%#]([^%#]*)[%#])?(#(.*)#)?', title)
        if m != None:
            self.consolidated = '連結' == m.group(6)
            self.fiscal_period_kind = gen_fiscal_period_kind(m) # don't know which forecast contained
            self.accounting_standards = m.group(4)
        elif ('業績予想' in title or '配当予想' in title or '配当の予想' in title):
            m = re.search(r'(第(.)四半期|中間)', title)
            if m is not None:   # 9691: 2024年３月期第２四半期連結累計期間業績予想の修正に関するお知らせ
                self.fiscal_period_kind = gen_fiscal_period_kind(m)
                self.consolidated = '連結' in title
                return
            # 業績予想及び配当予想の修正（特別配当）に関するお知らせ
            self.fiscal_period_kind = '0'
        elif ('剰余金の配当' in title):
            self.fiscal_period_kind = '0'
        elif ('業績' in title):
            self.fiscal_period_kind = '0'
        else:
            raise Exception("Unknown titile found!")

    def get_security_code(self):
        value = self.get_value("security_code")
        return value.value if value and len(value.value)>=4 else self.reader.xbrl_doc.company_code

    def get_company_name(self):
        value = self.get_value("company_name")
        return value.value if value else 'not found'

    @property
    def accounting_standard(self) -> Literal['jp','if','us']:
        std = 'jp'
        if self.reader.find_value_name(lambda x: x.endswith('IFRS')):
            std = 'if'
        elif self.reader.find_value_name(lambda x: x.endswith('US')):
            std = 'us'
        return std
    
    @property
    def reporting_date(self) -> ElementValue:
        wareki = {'令和': 2019, '平成': 1989, '昭和': 1926}
        def wareki2year(elemvalue):
            date1 = elemvalue.value.replace(' ','')
            for waname in wareki.keys():
                m = re.search(r'{}([0-9]+)年'.format(waname), date1)
                if m != None:
                    elemvalue.value = date1.replace(
                        waname+m.groups()[0],str(int(m.groups()[0])+wareki[waname]-1))
            return elemvalue

        if self.filling_date is not None:
            return wareki2year(self.filling_date)
        if self.forecast_correction_date is not None:
            return wareki2year(self.forecast_correction_date)
        if self.dividend_correction_date is not None:
            return wareki2year(self.dividend_correction_date)
        raise NameError('Reporting date not found')

    @property
    def reporting_iso_date(self) -> str:
        report_date = self.reporting_date.value
        m = re.search(r'([0-9]+)[年-]([0-9]+)[月-]([0-9]+)日?', report_date)
        if m is None:
            return self.reader.xbrl_doc.published_date[0].date().isoformat()
        return date(*(int(x) for x in m.groups())).isoformat()
    
    @property
    def forecast_period(self) -> str:
        # 'Role(Quarterly)?Forecasts' for (quarterly)? report which may have 業績予想
        # 'Role(Quarterly)?Dividends' for (quarterly)? report which may have 配当予想
        # 'Role(Non)?ConsolidatedInformationAnnual' for '業績予想の修正'
        # 'RoleRevisedDividendForecast' for '配当予想の修正'

        role = self.__find_role_name('fc_test')
        if len(role) <= 0: return 'Q2'
        return 'FY'

    @property
    def fiscal_year_end_date(self) -> datetime:
        value = self.get_value("fiscal_date_end")
        assert value is not None
        return datetime.strptime(value.value, "%Y-%m-%d")

    @property
    def fc_q2ytd_period(self) -> str:
        role = self.__find_role_name('fc_q2ytd')
        if len(role) <= 0: return ''
        return 'Q2'

    def fc(self,  latest_filter=False) -> Optional[DataFrame]:
        # year forecast:  'ForecastMemger','(Upper|Lower)Member' in member and 'CurrentYearDuration' = context
        # q2   forecast:  'ForecastMember','(Upper|Lower)Member' in member and 'CurrentAccumulatedQ2Duration' = context
        role = self.__find_role_name('fc')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri)
        if self.namespace_prefix=='tse-t-ed':
            pre_ver = self.reader.presentation_version()
            if pre_ver in ['2012-03-31', '2012-06-30']:
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_0_label': 'label'})
            elif pre_ver in ['2011-03-31', '2011-06-30']:
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_3_label': 'label'})
            else:
                assert pre_ver in ['2007-06-30', '2010-03-31']
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_2_label': 'label'})
        return fc if fc is None or not latest_filter else self.__filter_accounting_items(fc, consolidate_filter=True)

    def fc_dividends(self, latest_filter=False) -> Optional[DataFrame]:
        role = self.__find_role_name('fc_dividends')
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        fc = self.reader.read_value_by_role(role_uri)
        return fc if fc is None or not latest_filter else self.__filter_accounting_items(fc, consolidate_filter=False)
    
    def dividend_per_share(self, latest_filter=False) -> float:
        import numpy as np
        if self.namespace_prefix=='tse-t-ed':
            try:
                if self.ForecastDividendPerShare is not None:
                    return float(self.ForecastDividendPerShare.value)
                if self.ForecastUpperDividendPerShare is not None and self.ForecastLowerDividendPerShare is not None:
                    upper = float(self.ForecastUpperDividendPerShare.value)
                    lower = float(self.ForecastLowerDividendPerShare.value)
                    return (upper + lower)/2
            except ValueError:
                pass
            return np.nan
        fc_df = self.fc_dividends(latest_filter)
        if fc_df is None or fc_df.empty:
            return np.nan
        query_forecast_figures = 'value!="NaN"&member.str.contains("Forecast")&not member.str.startswith("Annual")'
        fc_df = fc_df.query(query_forecast_figures, engine='python')
        money = fc_df.query('data_type=="perShare"')[['name','value']].astype({'value':float})
        return money.query('name=="tse-ed-t:DividendPerShare"')['value'].sum()

    def q2ytd(self, latest_filter=False):
        role = self.__find_role_name('fc_q2ytd', latest_filter)
        if len(role) <= 0: return None
        role = role[0]
        role_uri = self.reader.get_role(role).uri

        q2ytd = self.reader.read_value_by_role(role_uri)
        return q2ytd if q2ytd is None or not latest_filter else self.__filter_accounting_items(q2ytd)

    def __filter_out_str(self) -> str:
        filter_out_str = 'NonConsolidated' if self.consolidated\
            else '(?<!Non)Consolidated'
        return filter_out_str

    def __filter_accounting_items(self, data:DataFrame, consolidate_filter=True) -> Optional[DataFrame]:
        if data.size == 0:
            return None
        
        # select consolidated type
        if len(data[data['consolidated']]) >= len(data[~data['consolidated']]):
            data = data[data['consolidated']]
        else:
            data = data[~data['consolidated']]

        # eliminate PreviousMember and filter YearDuration
        current_year_query = '~member.str.contains("Previous")&context.str.contains("Year.*Duration")'
        filtered = data.query(current_year_query, engine='python')
        # filter forecat members only
        forecast_query = 'value!="NaN"'
        if filtered[filtered['member']!=''].shape[0] > 0:
            forecast_query += '&(member.str.contains("Forecast")|member.str.contains("Lower")|member.str.contains("Upper"))'
        filtered = filtered.query(forecast_query, engine='python')
        return filtered

    def __find_role_name(self, finance_statement:str, latest_filter=False) -> list[str]:
        def consolidate_type_filter(roles):
            if not latest_filter:
                return roles
            filter_out_str = self.__filter_out_str()
            return [x for x in roles if not re.search(filter_out_str, x)]
        custom_role_keys = consolidate_type_filter(list(self.reader.custom_roles.keys()))
        roles = []
        for name in self.role_candidates[finance_statement]:
            roles += [x for x in custom_role_keys if name in x and x not in roles]
        return roles
    