from typing import Literal, Optional

import re
import warnings
import calendar
from datetime import date, datetime, timedelta
from pandas import DataFrame

from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.reader import Reader
from xbrr.xbrl.reader.element_value import ElementValue


class Forecast(BaseParser):
    tse_ed_t_table_candiates: dict[str, list[str]] = {
        'fc': ["ForecastsTable","InformationAnnualTable"],
        'fc_dividends': ["DividendsTable","DividendForecastTable"],
        'fc_q2ytd': ["InformationQ2YTDTable"],
    }
    tse_t_ed_table_candiates: dict[str, list[str]] = {
        'fc': ['ConsolidatedIncomeStatementsInformationAbstract','IncomeStatementsInformationAbstract'],
        'fc_dividends': ['ConsolidatedIncomeStatementsInformationAbstract','IncomeStatementsInformationAbstract'],
        'fc_q2ytd': [],
    }

    def __init__(self, reader:Reader):
        def gen_report_period_kind(m:re.Match[str]) -> str:
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

            "dividends_note": "tse-ed-t:NoteToDividends",
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
            self.table_candidates = self.tse_ed_t_table_candiates
        elif "tse-re-t"in reader.namespaces:
            super().__init__(reader, ElementValue, reit_tags)
            self.namespace_prefix = 'tse-re-t'
            self.table_candidates = self.tse_ed_t_table_candiates
        elif "tse-t-ed" in reader.namespaces:
            super().__init__(reader, ElementValue, tse_t_ed_tags)    # for old tdnet
            self.namespace_prefix = 'tse-t-ed'
            self.table_candidates = self.tse_t_ed_table_candiates

        if self.document_name is None:
            raise Exception("Unknown titile found!")

        self.__consolidated = None
        dic = str.maketrans('１２３４５６７８９０（）()［　］〔〕[]','1234567890####% %%%%%')
        title = self.document_name.value.translate(dic).strip().replace(' ','')
        m = re.search(r'(第(.)四半期|中間)?.*決算短信([%#]([^%#]*)[%#])?(#(.*)#)?', title)
        if m != None:
            self.__consolidated = '連結' == m.group(6)
            self.report_period_kind = gen_report_period_kind(m) # don't know which forecast contained
            self.accounting_standards = m.group(4)
        elif ('業績予想' in title or '配当予想' in title or '配当の予想' in title):
            m = re.search(r'(第(.)四半期|中間)', title)
            if m is not None:   # 9691: 2024年３月期第２四半期連結累計期間業績予想の修正に関するお知らせ
                self.report_period_kind = gen_report_period_kind(m)
                self.__consolidated = '連結' in title
                return
            # 業績予想及び配当予想の修正（特別配当）に関するお知らせ
            self.report_period_kind = '0'
        elif ('剰余金の配当' in title):
            self.report_period_kind = '0'
        elif ('業績' in title):
            self.report_period_kind = '0'
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
        try:
            report_date = self.reporting_date.value
            m = re.search(r'([0-9]+)[年-]([0-9]+)[月-]([0-9]+)日?', report_date)
            if m is not None:
                return date(*(int(x) for x in m.groups())).isoformat()
        except NameError:
            pass
        return self.reader.xbrl_doc.published_date[0].date().isoformat()
    
    @property
    def forecast_period(self) -> str:
        # 'Role(Quarterly)?Forecasts' for (quarterly)? report which may have 業績予想
        # 'Role(Quarterly)?Dividends' for (quarterly)? report which may have 配当予想
        # 'Role(Non)?ConsolidatedInformationAnnual' for '業績予想の修正'
        # 'RoleRevisedDividendForecast' for '配当予想の修正'

        if not self.find_role_name('fc') and not self.find_role_name('fc_dividends'):
            return 'Q2'
        return 'FY'

    @property
    def fiscal_year_start_date(self) -> date:
        end_date = self.fiscal_year_end_date
        assert end_date != None
        next_start_date = end_date + timedelta(days=1)
        return datetime(year=next_start_date.year-1, month=next_start_date.month, day=next_start_date.day)

    @property
    def fiscal_year_end_date(self) -> date:
        value = self.get_value("fiscal_date_end")
        assert value is not None
        return datetime.strptime(value.value, "%Y-%m-%d")

    @property
    def consolidated(self):
        try:
            return self.__consolidated if self.__consolidated else self.reader.xbrl_doc.consolidated
        except LookupError:
            cons_noncons = set([x['cons_nocons'] for x in self.reader.role_decision_info if 'table' in x])
            if 'NonConsolidatedMember' in cons_noncons and all([x not in cons_noncons for x in ['ConsolidatedMember','ConsNonconsMember']]):
                return False
            return True

    @property
    def forecast_year_start_date(self) -> date:
        start_date = self.fiscal_year_start_date
        assert start_date != None
        if self.reader.xbrl_doc.published_date[1] == 'a':
            start_date = datetime(year=start_date.year+1, month=start_date.month, day=start_date.day)
        return start_date

    @property
    def forecast_year_end_date(self) -> date:
        end_date = self.fiscal_year_end_date
        assert end_date != None
        if self.reader.xbrl_doc.published_date[1] == 'a':
            nextyear = end_date.year + 1
            end_date = date(year=nextyear, month=end_date.month,
                            day=calendar.monthrange(nextyear, end_date.month)[1])
        return end_date


    def fc(self,  latest2year=False) -> Optional[DataFrame]:
        role_uri = self.find_role_name('fc')
        if not role_uri:
            return None
        fc = self.reader.read_value_by_role(role_uri, report_start=self.forecast_year_start_date, report_end=self.forecast_year_end_date)
        if self.namespace_prefix=='tse-t-ed':
            pre_ver = self.reader.presentation_version()
            if pre_ver in ['2012-03-31', '2012-06-30']:
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_0_label': 'label'})
            elif pre_ver in ['2011-03-31', '2011-06-30']:
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_3_label': 'label'})
            else:
                assert pre_ver in ['2007-06-30', '2010-03-31']
                fc = fc.query('name.str.startswith("tse-t-ed:Forecast")').rename(columns={'label':'sub_label', 'parent_2_label': 'label'})
        return self.__filter_forecast_items_only(fc)

    def fc_dividends(self, latest2year=False) -> Optional[DataFrame]:
        role_uri = self.find_role_name('fc_dividends')
        if not role_uri:
            return None
        fc = self.reader.read_value_by_role(role_uri, report_start=self.forecast_year_start_date, report_end=self.forecast_year_end_date)
        return self.__filter_forecast_pershare_only(fc)
    
    def fc_dividends_note(self) -> Optional[str]:
        if self.dividends_note is None:
            return None
        return self.dividends_note.normalized_text.strip()
    
    def dividend_per_share(self, latest2year=False) -> float:
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

        fc_df = self.fc_dividends(latest2year)
        if fc_df is None or fc_df.empty:
            return np.nan
        
        # dividend per share name only
        fc_df = fc_df[fc_df['name']=="tse-ed-t:DividendPerShare"]
        # if Annual forecast exists, it is a forecast perShare value
        if fc_df[fc_df['member'].str.contains("Annual")].shape[0]>0:
            fc_df = fc_df[fc_df['member'].str.contains("Annual")]
        # if Annual forecast does not exist and Result exists, dividend split may happened
        else:
            analyzed = self.dividend_note()
            if analyzed and 'split_ratio' in analyzed and analyzed['split_ratio'] is not None \
                and analyzed['split_date'] > fc_df['period_start'].min():
                ratio = analyzed['split_ratio']
                adjustedDPS = fc_df[fc_df['member'].str.contains("SecondQuarter")].astype({'value':float})['value'].sum() / ratio
                forecastDPS = fc_df[fc_df['member'].str.contains("SecondQuarter")==False].astype({'value':float})['value'].sum()
                return adjustedDPS + forecastDPS
        
        money = fc_df[['name','value']].astype({'value':float})
        return money['value'].sum()
        
    def dividend_note(self) -> dict[str, Optional[object]]:
        return self.analyze_dividend_note_block(self.fc_dividends_note() or "")
    
    def analyze_dividend_note_block(self, text:str) -> dict[str, Optional[object]]:
        def is_split_mentioned(text: str) -> bool:
            return "株式分割" in text
        def _parse_split_date(text) -> Optional[date]:
            match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日.{0,10}効力発生日", text)
            if match:
                return datetime(int(match[1]), int(match[2]), int(match[3]))
            return None
        def parse_split_date(text) -> Optional[date]:
            # 日付パターンを抽出（例: 2025年4月1日）
            date_matches = re.findall(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text)
            for match in date_matches:
                y, m, d = map(int, match)
                date_obj = datetime(y, m, d)

                # 周辺の文脈に分割関連語があるか確認
                # 対象: その日付の前後50文字に「株式」「分割」「効力発生」「付」など
                pattern = f"{y}年\s*{m}月\s*{d}日"
                match_span = re.search(pattern, text)
                if match_span:
                    start = max(0, match_span.start() - 10)
                    end = match_span.end() + 10
                    context = text[start:end]
                    if re.search(r"(分割|効力発生|付|株式)", context):
                        return date_obj
            return None  # 該当なし        
        def parse_split_ratio(text) -> Optional[int]:
            match = re.search(r"1株.*?(\d{1,2})株", text)
            if match:
                return int(match[1])
            return None
        def check_split_affects_fiscal_year(split_date, fiscal_start, fiscal_end, text) -> bool:
            if not split_date:
                return False
            if fiscal_start <= split_date <= fiscal_end:
                if "分割後" in text or "考慮" in text or "単純合算ができない" in text:
                    return True
            return False

        text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        if not is_split_mentioned(text):
            return {}

        split_date = parse_split_date(text)
        split_ratio = parse_split_ratio(text)
        # affected = check_split_affects_fiscal_year(split_date, fiscal_start, fiscal_end, text)
        result = {
            "split_date": split_date.strftime('%Y-%m-%d') if split_date else "不明",
            "split_ratio": split_ratio,
            # "split_affects_fiscal_year": "✔️" if affected else "❌"
        }
        return result

    def q2ytd(self, latest2year=False):
        role_uri = self.find_role_name('fc_q2ytd')
        if not role_uri:
            return None
        q2ytd = self.reader.read_value_by_role(role_uri)
        return q2ytd if q2ytd is None or not latest2year else self.__filter_forecast_items_only(q2ytd)

    def find_role_name(self, finance_type:Literal['fc','fc_dividends','fc_q2ytd']) -> Optional[str]:
        scanstable = [x for x in self.reader.role_decision_info if 'table' in x]
        for table in self.table_candidates[finance_type]:
            for scan in scanstable:
                # fc_dividends may have NonConsolidatedMember even if the finance is ConsolidatedMember.
                if table in scan['table'] and \
                    (finance_type=='fc_dividends' or self.consolidated == (scan['cons_nocons']=="ConsolidatedMember")):
                    # (self.consolidated == (scan['cons_nocons']=="ConsolidatedMember") or scan['cons_nocons']=="ConsNonconsMember"):
                    return scan['xlink_role']
        return None

    def __filter_forecast_items_only(self, data:DataFrame) -> Optional[DataFrame]:
        if data.size == 0:
            return None
        
        # eliminate PreviousMember as previous forecast
        current_year_query = '~member.str.contains("Previous")'
        filtered = data.query(current_year_query, engine='python')
        # filter forecat members only, (eliminate current result)
        forecast_query = 'value!="NaN"'
        if filtered[filtered['member']!=''].shape[0] > 0:
            forecast_query += '&(member.str.contains("Forecast")|member.str.contains("Lower")|member.str.contains("Upper"))'
        filtered = filtered.query(forecast_query, engine='python')
        return filtered

    def __filter_forecast_pershare_only(self, data:DataFrame) -> Optional[DataFrame]:
        if data.size == 0:
            return None
        
        # perShare data type only
        filtered = data[data['data_type']=='perShare']
        # latest period_start only
        filtered = filtered[filtered['period_start']==filtered['period_start'].max()]
        # eliminate PreviousMember as previous forecast
        filtered = filtered[filtered['member'].str.contains("Previous")==False]
        # eliminate NaN value
        filtered = filtered[filtered['value']!="NaN"]
        return filtered
    