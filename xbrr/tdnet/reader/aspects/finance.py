from math import e
from typing import Optional, Literal, Callable, cast

from datetime import date, datetime, timedelta
import os
import calendar
import collections
import importlib
import importlib.util
import itertools
import re
import warnings
from bs4 import BeautifulSoup, Tag
import pandas as pd
from logging import getLogger

from pandas import DataFrame

if importlib.util.find_spec("pandas") is not None:
    import pandas as pd

from xbrr.base.reader.base_parser import BaseParser
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue


class Finance(BaseParser):

    def __init__(self, reader):
        tags = {
            "voluntary_accounting_policy_change": "jpcrp_cor:NotesVoluntaryChangesInAccountingPoliciesConsolidatedFinancialStatementsTextBlock",
            "segment_information": "jpcrp_cor:NotesSegmentInformationEtcConsolidatedFinancialStatementsTextBlock",
            "real_estate_for_lease": "jpcrp_cor:NotesRealEstateForLeaseEtcFinancialStatementsTextBlock",
            "accounting_standards": "jpdei_cor:AccountingStandardsDEI", # 会計基準 from metadata
            "_report_period_kind": "jpdei_cor:TypeOfCurrentPeriodDEI", # 会計期間 from metadata
            "_fiscal_year_start_date": "jpdei_cor:CurrentFiscalYearStartDateDEI",
            "_fiscal_year_end_date": "jpdei_cor:CurrentFiscalYearEndDateDEI",
            "company_name": "jpdei_cor:FilerNameInJapaneseDEI",

            # "_fiscal_year_end_date0": "tse-o-di:FiscalYearEnd",
            "report_FY": "tse-o-di:TypeOfReports-Annual",
            "report_Q1": "tse-o-di:TypeOfReports-FirstQuarter",
            "report_Q2": "tse-o-di:TypeOfReports-SecondQuarter",
            "report_Q3": "tse-o-di:TypeOfReports-ThirdQuarter",

            # old style xbrl
            # "consolidated_flag": "jpfr-di:ConsolidatedBSConsolidatedFinancialStatements",
            # new style xbrl
            "whether_consolidated": "jpdei_cor:WhetherConsolidatedFinancialStatementsArePreparedDEI",
        }

        self._YTD_role_piece = ["YearToQuarterEnd", "IncomeYTD"] # 四半期累計期間
        self._Quarter_period_role_piece = ["QuarterPeriod", "IncomeQuater"] # 四半期会計期間

        super().__init__(reader, ElementValue, tags)

    def get_security_code(self):
        return self.reader.xbrl_doc.company_code

    def get_company_name(self) -> str:
        value = self.get_value("company_name")
        return value.value if value else 'not found'

    @property
    def fiscal_year_start_date(self) -> date:
        value = self.get_value("_fiscal_year_start_date")
        if value is not None:
            return datetime.strptime(value.value, "%Y-%m-%d").date()
        return self._get_fiscal_year_start_date_from_context()

    @property
    def fiscal_year_end_date(self) -> date:
        value = self.get_value("_fiscal_year_end_date")
        if value is not None:
            return datetime.strptime(value.value, "%Y-%m-%d").date()
        else:  # backward compatibility for old style xbrl
            return self._get_fiscal_year_end_date_from_reporting_info()
            value = self.get_value("_fiscal_year_end_date0")
            return datetime.strptime(value.value, "%Y-%m-%d").date() if value else self._get_fiscal_year_end_date_from_reporting_info()

    @property
    def report_period_end_date(self) -> date:
        return self.reader.xbrl_doc.report_period_end_date

    @property
    def reporting_iso_date(self) -> str:
        return self.reader.xbrl_doc.published_date[0].date().isoformat()

    @property
    def report_period_kind(self) -> ElementValue:
        if self._report_period_kind is not None:
            return self._report_period_kind
        if self.report_Q1 and self.report_Q1.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q1")
        if self.report_Q2 and self.report_Q2.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q2")
        if self.report_Q3 and self.report_Q3.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Q3")
        if self.report_FY and self.report_FY.value=='true':
            return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="FY")
        return ElementValue("jpdei_cor:TypeOfCurrentPeriodDEI", value="Qx")

    @property
    def consolidated(self) -> bool:
        return self.reader.xbrl_doc.consolidated

    def bs(self, latest2year=False) -> DataFrame:
        def convert_parallel_bs_to_serial(soup:BeautifulSoup):
            # soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return "テーブルが見つかりませんでした。"

            rows = table.find_all('tr')
            
            # ----------------------------------------------------
            # 1. 並列記載（横並び）の判定
            # ----------------------------------------------------
            is_parallel = False
            for row in rows:
                text = row.get_text()
                # 資産合計と負債・資本合計が同じ行に含まれているかチェック
                if '資産合計' in text and '負債・資本合計' in text:
                    is_parallel = True
                    break
                    
            if not is_parallel:
                return
            
            self.logger.warning("【判定結果】並列記載のBSであることを検出しました。直列に変換します。")

            # ----------------------------------------------------
            # 2. 入力テーブルのヘッダー行から情報を動的に抽出
            # ----------------------------------------------------
            # 通常、並列BSのヘッダーは1行目（大分類）や2行目（科目・日付）にあります。
            # 3行目以降からデータが始まると仮定し、最初の2行からヘッダー情報を動的に取得します。
            
            # 日付や「科目」という列名が含まれる詳細ヘッダー行（通常2行目）から動的に取得
            dynamic_headers = ["科目", "前結会計年度末", "当連結会計期間末"] # フォールバック用
            if len(rows) > 1:
                second_row_cols = [td.get_text(strip=True) for td in rows[1].find_all(['td', 'th'])]
                # 左側（資産側）の3列分をそのまま新テーブルのヘッダーとして抽出
                if len(second_row_cols) >= 3:
                    dynamic_headers = second_row_cols[:3]

            # ----------------------------------------------------
            # 3. データの抽出と分離
            # ----------------------------------------------------
            assets_data = []      # 左側：資産の部
            liabilities_data = [] # 右側：負債・資本の部
            
            # ヘッダー情報の取得（最初の2行を想定）
            header_rows = rows[:2]
            
            # データ行の処理
            for row in rows[2:]:
                cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                
                # 横並びの列数が十分にない場合はスキップまたは特殊処理
                if len(cols) < 6:
                    continue
                    
                # 左側（資産）: 科目, 前期末, 当期末
                asset_item = cols[0]
                asset_val1 = cols[1]
                asset_val2 = cols[2]
                
                # 右側（負債・資本）: 科目, 前期末, 当期末
                liab_item = cols[3]
                liab_val1 = cols[4]
                liab_val2 = cols[5]
                
                # 空白行でなければそれぞれのリストに追加
                if asset_item:
                    assets_data.append([asset_item, asset_val1, asset_val2])
                if liab_item:
                    liabilities_data.append([liab_item, liab_val1, liab_val2])

            # ----------------------------------------------------
            # 4. 直列（縦並び）HTMLテーブルの再構築
            # ----------------------------------------------------
            new_soup = BeautifulSoup('<table></table>', 'html.parser')
            new_table = new_soup.table
            
            # 共通ヘッダー（科目、2024年3月31日、2024年9月30日）を生成
            # ※元のヘッダーから適切な期間名などを抽出して設定するとより正確になります
            thead = new_soup.new_tag('tr')
            for h_text in dynamic_headers:
                th = new_soup.new_tag('th')
                th.string = h_text
                thead.append(th)
            new_table.append(thead)

            # --- 資産の部 ---
            for row_data in assets_data:
                tr = new_soup.new_tag('tr')
                for val in row_data:
                    td = new_soup.new_tag('td')
                    p = new_soup.new_tag('p')
                    p.string = val
                    td.append(p)
                    tr.append(td)
                new_table.append(tr)

            # --- 負債・資本の部 ---
            for row_data in liabilities_data:
                tr = new_soup.new_tag('tr')
                for val in row_data:
                    td = new_soup.new_tag('td')
                    p = new_soup.new_tag('p')
                    p.string = val
                    td.append(p)
                    tr.append(td)
                new_table.append(tr)

            table.insert_after(new_table)  # 新しいテーブルを挿入
            table.decompose()  # 元のテーブルを削除
            return soup

        role_uri = self.find_role_name('bs', latest2year)
        if not role_uri:
            textblock = self.read_value_by_textblock('bs')
            if textblock is None:
                self.logger.warning("BSのテキストブロックが見つかりませんでした。")
                return pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])
            soup = textblock.html
            convert_parallel_bs_to_serial(soup)
            return self.__read_finance_statement(soup)

        bs = self.reader.read_value_by_role(role_uri, report_end=self.report_period_end_date)
        return self.__df_instant(bs, latest2year)

    def pl(self, latest2year=False) -> DataFrame:
        fix_cal = ['<GrossProfit','OperatingGrossProfit','GrossProfitIFRS',  # GrossProfitOn: 1967:2017-04-28, GrossProfitNetGP
                   'GrossProfitNetGP',
                   '<OperatingIncome','OperatingProfitLossIFRS','~(?<!Non)(?<!Other)OperatingIncome','NormalizedOperatingProfitIFRS',
                   'OrdinaryIncome','OrdinaryIncomeBNK','>OrdinaryProfitLoss','~(Operating|Ordinary)[Ll]oss$',
                   'ProfitLossBeforeTax','ProfitLossBeforeTaxIFRS','IncomeBeforeIncomeTaxes',  # 2282:2022-05-10
                   'BusinessProfitLossIFRS','BusinessProfitPLIFRS','~Profit$', 'ProfitLoss'] # BusinessProfitPLIFRS 7951:2019-08-01, ~[Ll]oss$: 6084:2014-08-14

        role_uri = self.find_role_name('pl', latest2year, exclusion=self._Quarter_period_role_piece)
        if not role_uri:
            textblock = self.read_value_by_textblock('pl')
            return self.__read_finance_statement(textblock.html) if textblock is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        pl = self.reader.read_value_by_role(role_uri, fix_cal_node=fix_cal, report_start=self.fiscal_year_start_date, report_end=self.report_period_end_date)
        return self.__df_duration_from_fiscal_year_start_date(pl, latest2year)

    def cf(self, latest2year=False) -> DataFrame:
        role_uri = self.find_role_name('cf', latest2year)
        if not role_uri:
            textblock = self.read_value_by_textblock('cf')
            if textblock is not None:
                return self.__read_finance_statement(textblock.html)
            
            cf_note_df = self.cf_note(latest2year)
            return cf_note_df if cf_note_df is not None\
                else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

        cf = self.reader.read_value_by_role(role_uri, report_start=self.fiscal_year_start_date, report_end=self.report_period_end_date)
        return self.__df_duration_from_fiscal_year_start_date(cf, latest2year)

    def cf_note(self, latest2year=False) -> Optional[DataFrame]:
        """四半期決算短信のHTMLからキャッシュ・フロー注記の減価償却費を抽出する

        Returns:
            DataFrame | None: 抽出された減価償却費を含むCF中期のDataFrame。見つからない場合はNone。
        """
        def item_and_parents_next_siblings(element):
            # 1. 現在の要素を返す
            yield element
            # 2. まず現在の要素の次の兄弟を返す
            for sib in element.next_siblings:
                if isinstance(sib, Tag):
                    yield sib
            # 3. 親を遡りながら、それぞれの次の兄弟を返す
            for parent in element.parents:
                if parent.name == '[document]':
                    break
                for sib in parent.next_siblings:
                    if isinstance(sib, Tag):
                        yield sib

        def unnest_tables(soup, outer_table):
            # soup = BeautifulSoup(html_content, 'html.parser')
            main_table = outer_table
            
            if not main_table:
                return

            # 親table内の各行を処理
            # (親の直下trのみを取得するために recursive=False または親要素をチェック)
            parent_trs = [tr for tr in main_table.find_all('tr') if tr.find_parent('table') == main_table]

            for tr in parent_trs:
                # この行の中に含まれる入れ子テーブルを探す
                nested_tables = tr.find_all('table')
                
                if not nested_tables:
                    continue  # 入れ子テーブルがなければそのまま
                    
                # 入れ子テーブルの「最大行数」を算出
                # (行数が崩れていない＝すべての入れ子テーブルの行数は同じはずですが、念のため取得)
                max_nested_rows = max(len(table.find_all('tr')) for table in nested_tables)
                
                # 展開用の新しい行（<tr>）のリストを作成
                expanded_trs = [soup.new_tag('tr') for _ in range(max_nested_rows)]
                
                # 親行（tr）内の直下のセル（td / th）を順番に処理
                cells = tr.find_all(['td', 'th'], recursive=False)
                for cell in cells:
                    nested_table = cell.find('table')
                    
                    if nested_table:
                        # --- セルの中に入れ子テーブルがある場合 ---
                        nested_rows = nested_table.find_all('tr')
                        for i, n_tr in enumerate(nested_rows):
                            # 入れ子テーブルの各行からすべてのtd/thを取得し、新行に追加
                            for n_cell in n_tr.find_all(['td', 'th'], recursive=False):
                                expanded_trs[i].append(n_cell.extract())
                    else:
                        # --- 通常のセルの場合 ---
                        # 入れ子テーブルの行数分縦結合（rowspan）させるか、最初の行に配置して残りを空ける処理
                        # ここでは最初の行に元のセルを入れ、残りの行にはrowspanを設定
                        cell['rowspan'] = str(max_nested_rows)
                        expanded_trs[0].append(cell.extract())
                        
                # 元の親行（tr）を、展開した複数行（expanded_trs）に置換
                for new_tr in reversed(expanded_trs):
                    tr.insert_after(new_tr)
                tr.decompose()  # 元の親行を削除

        # 1. ファイルの存在確認と読み込み
        qualitative_soup = self.reader.xbrl_doc.read_file("qualitative.htm")

        cf_title_pattern = re.compile(r"キャッシュ・フロー(計算書)?(に関する注記|関係)") # 関係:3222,8570,8628,2220,9502,1965  計算書なし:4413,414A,8697,6617
        cf_nodepre_pattern = re.compile(r"減価償却費[^。]*(ありません。|記載を省略|発生しておりません。)")

        target_heading = None
        # 2. ターゲットとなる見出しを下から探す（目次スキップのため）
        for heading in qualitative_soup.find_all(["h1", "h2", "h3", "h4", "p", "div"])[::-1]:
            text = heading.get_text(strip=True)

            # 「四半期キャッシュ・フロー計算書に関する注記」を含み、かつ目次の特徴（目次という単語やリーダー線）を持たないものを選択
            if cf_title_pattern.search(text):
                if "目次" in text or "…" in text or "..." in text:
                    continue  # 目次用の行ならスキップ
                target_heading = heading
                break

        if not target_heading:
            if self.report_period_end_date.year >= 2025:
                self.logger.warning("本文内のキャッシュ・フロー計算書に関する注記」セクションが見つかりませんでした。")
            return None

        # 2. 後続にTableがある場所を正確に探す
        for elem in item_and_parents_next_siblings(target_heading):
            if elem.find_all(['table']):
                target_heading = elem
                break
            if cf_nodepre_pattern.search(re.sub(r"[\(（][^)）]*?[\)）]","",elem.get_text())): # 4424:2026-02-12 セクションはあるがTableが無い場合,TODO 減価償却費を０（今回、前回）にする
                target_heading = None
                break

        if not target_heading:
            self.logger.warning("本文内のキャッシュ・フロー計算書に関する注記」Tableが見つかりませんでした。")
            prioryear = self.report_period_end_date.year - 1
            priordate = date(year=prioryear, month=self.report_period_end_date.month,
                                day=calendar.monthrange(prioryear, self.report_period_end_date.month)[1]).strftime("%Y-%m-%d")
            return pd.DataFrame(
                [
                    ["減価償却費", "0", "JPY", "0", "Prior1YTDDuration", "monetary","dummy", "1", True, priordate],
                    ["減価償却費", "0", "JPY", "0", "CurrentYTDDuration","monetary","dummy", "1", True, self.report_period_end_date.strftime("%Y-%m-%d")]
                ],
                columns=['label','value','unit','indent','context','data_type','name','depth','consolidated','period']
            )

        # 1. すべての内側の表（table）をループ処理
        outer_table = target_heading.find("table")
        unnest_tables(qualitative_soup, outer_table)

        # 3. 一つのセルに複数データを記載している場合は、TRで行を分離する
        tbody = target_heading.find('tbody')
        body = tbody if tbody else target_heading
        # trの中のすべてのtdが2つ以上の同数のｐタグを持つ場合
        for tr in body.find_all('tr'):
            if all(len(td.find_all('p')) > 1 for td in tr.find_all('td')):
                # brタグで分割して新しいtrを作成
                new_trs = {}
                for td in tr.find_all('td'):
                    for i,p in enumerate(td.find_all('p')):
                        new_tr = new_trs.setdefault(i, qualitative_soup.new_tag('tr'))
                        new_td = qualitative_soup.new_tag('td')
                        new_td.append(p)
                        new_tr.append(new_td)
                # 元のtrの直前に新しいtrを追加
                for new_tr in new_trs.values():
                    tr.insert_before(new_tr)
                tr.decompose()

        return self.__read_finance_statement(target_heading)
    
    def __df_duration_from_fiscal_year_start_date(self, df:DataFrame, latest2year:bool) -> DataFrame:
        if 'context' in df.columns:
            fy_start = self.fiscal_year_start_date
            month_day = fy_start.strftime('%m-%d')
            df = df[(df['context'].str.endswith('Duration'))&(df['period_start'].str.endswith(month_day))]
            if latest2year:
                df = df[(~df['context'].str.startswith('Prior2')) & (~df['context'].str.startswith('Prior3'))]
        return df if not df.empty else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])
    
    def __df_instant(self, df:DataFrame, latest2year:bool) -> DataFrame:
        if 'context' in df.columns:
            df = df[(df['context'].str.endswith('Instant'))&(~df['context'].str.startswith('Prior1Quarter'))]
            if latest2year:
                df = df[(~df['context'].str.startswith('Prior2')) & (~df['context'].str.startswith('Prior3'))]
        return df if not df.empty else pd.DataFrame(columns=['label', 'value', 'unit', 'context', 'data_type', 'name', 'depth', 'consolidated'])

    def scan_presentation(self) -> list[BaseReader.PreTable|BaseReader.PreHeading]:
        return self.reader.role_decision_info

    def find_role_name(self, finance_type:Literal['bs','pl','cf'], latest2year:bool=False, exclusion:list[str]=[]) -> Optional[str]:
        scanstable = [x for x in self.scan_presentation() if 'table' in x]
        # old style presentation before 2014
        if all([x['table']=='' for x in scanstable]):
            return self.find_role_name2013(scanstable, latest2year, finance_type)
        # current style presentation after 20140116
        assert any([x['table']!='' for x in scanstable])
        return self.find_role_nameXXXX(scanstable, finance_type, latest2year, exclusion)

    def find_role_nameXXXX(self, scans:list[BaseReader.PreTable], finance_type:Literal['bs','pl','cf'], latest2year:bool, exclusion:list[str]) -> Optional[str]:
        table_candidates = {
            'jp': {  # Japanese GAAP
                'bs': ['BalanceSheetTable'],
                'pl': ['StatementOfIncomeTable'],
                'cf': ['StatementOfCashFlowsTable'],
                'che': ['StatementOfChangesInEquityTable'],

            },
            'if': {  # IFRS
                'bs': ['StatementOfFinancialPositionIFRSTable'],
                'pl': ['StatementOfProfitOrLossIFRSTable', 'StatementOfComprehensiveIncomeIFRSTable'],  # StatementOfProfitOrLossIFRSTable from 2019-04-23, StatementOfComprehensiveIncomeIFRSTable without ProfitOrLossIFRSTable from 2019-04-25
                'cf': ['StatementOfCashFlowsIFRSTable'],
                'che': ['StatementOfChangesInEquityTable', 'StatementOfChangesInEquityIFRSTable'],
            },
            'us': {  # US GAAP
                'bs': ['BalanceSheetTable'],
                'pl': ['StatementOfIncomeTable'],
                'cf': ['StatementOfCashFlowsTable'],
                'che': ['StatementOfChangesInEquityTable'],
            }
        }
        accounting_standards = self.reader.xbrl_doc.accounting_standard

        consolidated_switch = self.consolidated
        if latest2year: # check other [non]consolidated because this is the first year case after changing [non]consolidated accounting
            if not any([self.consolidated==(s['cons_nocons']=="ConsolidatedMember") for s in scans if s['table'] in table_candidates[accounting_standards]['pl']
                    and not any([ex in s['xlink_role'] for ex in exclusion])]) and \
                any([self.consolidated==(s['cons_nocons']=="ConsolidatedMember") for s in scans if s['table'] in table_candidates[accounting_standards]['bs']
                    and not any([ex in s['xlink_role'] for ex in exclusion])]):
                consolidated_switch = not self.consolidated

        for table in table_candidates[accounting_standards][finance_type]:
            for scan in scans:
                if table == scan['table'] and consolidated_switch == (scan['cons_nocons']=="ConsolidatedMember"):
                    if any([ex in scan['xlink_role'] for ex in exclusion]):
                        continue
                    return scan['xlink_role']
        return None

    def find_role_name2013(self, scans:list[BaseReader.PreTable], latest2year:bool, finance_type:Literal['bs','pl','cf']) -> Optional[str]:
        table_candidates2013 = {
            'bs': ['BalanceSheets'],
            'pl': ['StatementsOfIncomeYTD','StatementsOfIncome'],
            'cf': ['StatementsOfCashFlows'],
            'cha': ['StatementsOfChangesInNetAssets'],
        }
        consolidated_switch = self.consolidated
        if latest2year: # check other [non]consolidated because this is the first year case after changing [non]consolidated accounting
            if not any([(not self.consolidated) == ('NonConsolidated' in s['xlink_role'].split(t)[0]) for s in scans for t in table_candidates2013['pl'] if t in s['xlink_role']]) and \
                any([(not self.consolidated) == ('NonConsolidated' in s['xlink_role'].split(t)[0]) for s in scans for t in table_candidates2013['bs'] if t in s['xlink_role']]):
                consolidated_switch = not self.consolidated

        for table in table_candidates2013[finance_type]:
            for scan in scans:
                if table in scan['xlink_role'] and \
                    (not consolidated_switch) == ('NonConsolidated' in scan['xlink_role'].split(table)[0]):   # ConsolidatedXXX, ConsolidatedQuarterlyXXX
                    return scan['xlink_role']
        return None

    def read_value_by_textblock(self, finance_type:Literal['bs','pl','cf']) -> Optional[ElementValue]:
        textblock_candidates = {
            'bs': ['BalanceSheetHeading'], #,'StatementOfFinancialPositionIFRSHeading']) # 
            'pl': ['StatementOfIncomeHeading','StatementOfProfitOrLossIFRSHeading','StatementOfComprehensiveIncomeSingleStatementHeading'], # StatementOfComprehensiveIncomeSingleStatementHeading:6464:2018-02-14
            'cf': ['StatementOfCashFlowsHeading','StatementOfCashFlowsIFRSHeading'],
        }
        scansheading = [x for x in self.reader.role_decision_info if 'heading' in x]
        for heading in textblock_candidates[finance_type]:
            scans = [s for s in scansheading if heading in s['heading'] and self.consolidated == (s['cons_nocons']=='Consolidated')]
            if len(scans) == 1:
                textblock_name = ':'.join(scans[0]['xlink_href'].split('_', 2))
                textblock = self.reader.findv(textblock_name)
                return textblock
            for scan in scans:
                if 'YearToQuarter' in scan['xlink_href']:
                    textblock_name = ':'.join(scan['xlink_href'].split('_', 2))
                    textblock = self.reader.findv(textblock_name)
                    return textblock
                self.logger.warning("Multiple text blocks found for heading: {}".format(heading))
        return None

    def __read_finance_statement(self, statement_xml):
        def myen(vtext, unit):
            if vtext in ['－', '-', '―'] or len(vtext)==0:
                return ''
            if vtext.endswith('円'):    # 円で終わるとき数字・カンマ以外を除去。unitはanalyze_unit_till_tableで取得済み
                vtext = re.sub(r"[^\d,]", "", vtext)
            myen = vtext.translate(str.maketrans({',':None, '△':'-', '(': None, ')':None})) + unit # '△':'-': 99830:2019-04-11
            return myen
        def isnum(myen):
            try:
                float(myen)
            except ValueError:
                return False
            else:
                return True
        def label_margin(columns):
            label = ''.join([re.sub(r"[\d,百万千円]","",x.text.strip()) for x in columns[0].select('p')])
            if label != '' and columns[0].get('colspan',"") == '': # column0 has label
                style_str = columns[0].find('p').get('style',"") if label != "" else ""
                m = re.match(r'.*-left: *([0-9]*).?[0-9]*p[tx].*', style_str)
                margin = m.groups()[0] if m is not None else "0"
            else: # columns construct the label structure
                margin = 0
                for margin in range(0,len(columns)+prevcol):
                    label = ''.join([x.text.strip() for x in columns[margin].select('p')])
                    if label!='': break
            return (label.replace(' ','').replace('\u3000',''), margin)
        def get_value(column):
            text = column.text.strip()
            tokens = re.split('[ \xa0\n]', text)
            value = myen(tokens[-1], unit)
            return value if isnum(value) or value=='' else text
        indent_state = []
        def indent_label(margin_left):
            delidx = [i for i,x in enumerate(indent_state) if int(x) > int(margin_left)]
            if len(delidx) > 0: del indent_state[delidx[0]:]
            indent_state.append(margin_left)
            c = collections.Counter(indent_state)
            ks = sorted(c.keys(), key=int)
            return "-".join([str(c[x]) for x in ks])
        def analyze_title(columns, thiscol, prevcol, this_str, prev_str):
            def col_year(c):
                years = [int(x) for x in re.split(r'[^\d]',c.text) if x!='' and int(x)>1900]
                if c.text.strip().startswith('前') and '増減' not in c.text:
                    return 7777
                elif c.text.strip().startswith('当'):
                    return 9999
                elif years:
                    return years[0]
                return -1
            colindex = list(itertools.accumulate([int(c.get('colspan','1')) for c in columns]))
            year_index = sorted([(col_year(c),colindex[i-1]-colindex[-1]) for i,c in enumerate(columns) if col_year(c)>0], key=lambda x: x[0])
            if len(year_index) > 0: thiscol = year_index[-1][1]
            if len(year_index) > 1:
                prevcol = year_index[-2][1]
                if year_index[-1][0]==7777: thiscol, prevcol = prevcol, thiscol # when exist '前' and not exist '当'
            return thiscol, prevcol
        def analyze_column(label, columns, tc, pc):
            def adjust(columns, idx):
                for i in range(3):
                    if re.sub(r"[,百万千円]","",columns[idx+i].text.strip()).isdigit():
                        return i
                return 0
            if len(label) > 2 and not any([c in label for c in '([/#,.])']):
                return tc + adjust(columns, tc), pc + adjust(columns, pc)
            return tc, pc
        def analyze_unit(elemlist, unit):
            for c in elemlist:
                text = c.text.strip()
                if '百万円' in text:
                    return '000000'
                elif '千円' in text:
                    return '000'
                elif '円' in text:
                    return ''
            return unit
        def analyze_unit_till_table(soup):
            list = []
            for elem in soup.find_all(True):
                if elem.name == 'table':
                    list.append(elem)
                    break
                if elem.name is not None: list.append(elem)
            return analyze_unit(list, '000000')

        thiscol, prevcol = -1, -2
        unit = analyze_unit_till_table(statement_xml)
        values = []
        # 親（ancestors）に 'table' がないものだけを抽出
        outer_tables = statement_xml.find_all(
            lambda tag: tag.name == "table" and not tag.find_parent("table")
        )
        for table in outer_tables:
            if (thead := table.find('thead', recursive=False)):
                for record in thead.find_all('tr', recursive=False):
                    columns = list(record.find_all('td', recursive=False))
                    if len(values)==0:
                        this_str = str(self.report_period_end_date.year)
                        prev_str = str(int(this_str)-1)
                        thiscol, prevcol = analyze_title(columns, thiscol, prevcol, this_str, prev_str)
            tbody = _tbody if (_tbody:=table.find('tbody', recursive=False)) else table
            for record in tbody.find_all('tr', recursive=False):
                columns = list(record.find_all('td', recursive=False))
                if len(columns) < max(abs(thiscol), abs(prevcol))+1:
                    unit = analyze_unit(columns, unit)
                    continue
                label, margin = label_margin(columns)
                if len(values)==0: thiscol,prevcol = analyze_column(label, columns, thiscol, prevcol)
                value = get_value(columns[thiscol])

                if label != "" and value == "": # skip headding part
                    # label+"合計"でここから始まるブロックが終わるという規約であれば、depthに依存関係を入れられる
                    indent = indent_label(margin)
                elif isnum(value):
                    if '.' in value or label == '': continue   # skip float value １株当たり四半期利益
                    prev_value = get_value(columns[prevcol])
                    indent = indent_label(margin)
                    depth = len(indent.split('-'))
                    if isnum(prev_value):
                        prioryear = self.report_period_end_date.year - 1
                        values.append({
                            'label': label,
                            'value': prev_value,
                            'unit': 'JPY',
                            'indent': indent,
                            'context': 'Prior1YTDDuration',
                            'data_type': 'monetary',
                            'name': "dummy",
                            'depth': str(depth),
                            'consolidated': True,
                            'period': date(year=prioryear, month=self.report_period_end_date.month,
                                            day=calendar.monthrange(prioryear, self.report_period_end_date.month)[1]).strftime("%Y-%m-%d")
                        })
                    values.append({
                        'label': label,
                        'value': value,
                        'unit': 'JPY',
                        'indent': indent,
                        'context': 'CurrentYTDDuration',
                        'data_type': 'monetary',
                        'name': "dummy",
                        'depth': str(depth),
                        'consolidated': True,
                        'period': self.report_period_end_date.strftime("%Y-%m-%d")
                    })
                else:
                    # assert label=='' or value=='' or any(['円' in x.text for x in columns]) or any([x.text.strip().startswith('当') for x in columns]) #'当連結会計年度' in value
                    unit = analyze_unit(columns, unit)
                    # if value.startswith('当'): #'当連結会計年度' in value
                    if len(values)==0:
                        this_str = str(self.report_period_end_date.year)
                        prev_str = str(int(this_str)-1)
                        thiscol, prevcol = analyze_title(columns, thiscol, prevcol, this_str, prev_str)
        headers = ['label','value','unit','indent','context','data_type','name','depth','consolidated','period']
        return pd.DataFrame(values, columns=headers).drop_duplicates(subset=['label', 'context'], keep='first')

    def _get_fiscal_year_end_date_from_reporting_info(self) -> date:
        """
        Get fiscal year end date from reporting information
        """
        import calendar
        def get_last_date_of_month(dt: date|datetime) -> date:
            return dt.replace(day=calendar.monthrange(dt.year, dt.month)[1])

        rped = self.report_period_end_date
        kind:str = self.report_period_kind.value
        if kind == "Q1":
            return get_last_date_of_month(rped + timedelta(days=365*3/4))
        elif kind == "Q2":
            return get_last_date_of_month(rped + timedelta(days=365/2))
        elif kind == "Q3":
            return get_last_date_of_month(rped + timedelta(days=365/4))
        return rped
