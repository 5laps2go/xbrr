import os
import shutil
import unittest
from xbrr.tdnet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.tdnet.reader.doc import Doc
from xbrr.tdnet.reader.aspects.forecast import Forecast

class TestForecast(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        client = DocumentClient()
        # "081220210818487667" Ｊ－共和工業 2022年4月期 第1四半期決算短信〔日本基準〕（連結）
        # root_dir = client.get_xbrl("081220210818487667", save_dir=_dir,
        #                            expand_level="dir")
        root_dir = os.path.join(_dir, "081220210818487667")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="summary")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        # shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_accounting_standards(self):
        feature = self.reader.extract(Forecast).accounting_standards
        self.assertEqual(feature, "日本基準")
        feature = self.reader.extract(Forecast).consolidated
        self.assertTrue(feature)

    def test_report_period_kind(self):
        feature = self.reader.extract(Forecast).report_period_kind
        self.assertEqual(feature, "Q1")

    def test_roles(self):
        roles = self.reader.custom_roles
        self.assertTrue(len(roles) > 0)
        self.assertIn('RoleBusinessResultsQuarterlyOperatingResults', roles)    # 四半期経営成績
        self.assertIn('RoleBusinessResultsQuarterlyFinancialPositions', roles)  # 四半期財政状態
        self.assertIn('RoleQuarterlyDividends', roles)                          # 配当の状況
        self.assertIn('RoleQuarterlyForecasts', roles)                          # 四半期業績予想

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertTrue(len(namespaces) > 0)
        self.assertIn('tse-ed-t', namespaces)
        # self.assertIn('tse-qcedjpsm-15150', namespaces)

    def test_fc(self):
        fc = self.reader.extract(Forecast).fc()
        # fc.to_csv(os.path.join(self._dir, 'test_fc.csv'))
        self.assertTrue(fc is not None)
        self.assertGreater(len(fc), 0)

    def test_dividend_per_share(self):
        dps = self.reader.extract(Forecast).dividend_per_share()
        self.assertIsInstance(dps, float)
        self.assertAlmostEqual(dps, 80.0)

    def test_dividend_per_share_split_affects_fiscal_year(self):
        _dir = os.path.join(os.path.dirname(__file__), "/tmp")
        client = DocumentClient()
        # 住友林業 2025年12月期第2四半期(中間期)決算短信〔日本基準〕(連結)
        root_dir = client.get_xbrl("081220250807534279", save_dir=_dir, expand_level="dir")
        xbrl_doc = Doc(root_dir=str(root_dir), xbrl_kind="summary")
        reader = Reader(xbrl_doc, save_dir=_dir)
        result = reader.extract(Forecast).dividend_note()
        self.assertDictEqual(result, {"split_date": "2025-07-01", "split_ratio": 3})
        dps = reader.extract(Forecast).dividend_per_share()
        self.assertIsInstance(dps, float)
        self.assertAlmostEqual(dps, 50.0)

    def test_analyze_dividend_note_block(self):
        text_blocks = [
            """""",
            """(注１) 2024年３月期の期末配当は、2024年５月17日に開催予定の当社取締役会に付議する予定です。(注２) 上記「配当の状況」は、普通株式に係る配当の状況です。社債型種類株式の配当の状況については、後述の「社債型種類株式の配当の状況」をご参照ください。(注３) 2024年６月20日に開催予定の当社第38回定時株主総会において定款変更に関する議案が承認可決されることを条件に、2024年10月１日を効力発生日として、普通株式１株につき10株の割合をもって分割する予定です。上記の2025年３月期(予想)については、第２四半期末は分割前、期末は分割後の金額を記載しています。年間の配当予想については、当該株式分割の実施により単純合計ができないため、表示していません。なお、当該株式分割を考慮しない場合の年間配当金は86円です。""",
            """※　2025年６月30日を基準日、2025年７月１日を効力発生日として、普通株式１株につき３株の割合で株式分割を行っております。上記の2025年12月期（予想）の１株当たり期末配当金は株式分割考慮後の金額を記載しております。2025年12月期（予想）の１株当たり年間配当金合計は、株式分割の実施により、中間配当金と期末配当金との単純合算ができないため記載しておりません。なお、株式分割を考慮しない場合の2025年12月期（予想）の１株当たり期末配当金は75円00銭、年間配当金合計は150円00銭となります。""",
            """2．当社は、2025年4月1日を効力発生日として、普通株式1株につき5株の割合で株式分割を実施しました。2025年3月期については、当該株式分割前の実際の配当金の額を記載しています。""",
            """(注）当社は、2025年４月１日付で普通株式１株につき２株の割合で株式分割を行っております。2025年３月期については、当該株式分割前の実際の配当金の額を記載しております。2026年３月期（予想）については、株式分割後の数値を記載しております。""",
            """（注）１ 直近に公表されている配当予想からの修正の有無：無２ 当社は、2024年10月１日を効力発生日として、普通株式１株につき２株の割合で株式分割を実施する予定であります。2023年９月期、2024年９月期の配当金の額は、当該株式分割前の配当金の額を記載しております。""",
            """(注)直近に公表されている配当予想からの修正の有無：無※１中間配当金は普通配当18円、記念配当２円、期末配当金は普通配当18円、記念配当２円であります。※２当社は、2025年９月１日を効力発生日として、普通株式１株につき３株の割合で株式分割を行う予定です。中間配当金は20円、期末配当金は当該株式分割の影響を考慮した金額７円を記載しております。また、年間配当金の合計につきましては、株式分割により単純比較ができないため表示しておりません。なお、当該株式分割を考慮しない場合の期末配当金は21円、年間配当金は41円となります。""",
        ]
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[0])
        self.assertEqual(result, None)
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[1])
        self.assertDictEqual(result, {"split_date": "2024-10-01", "split_ratio": 10})
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[2])
        self.assertDictEqual(result, {"split_date": "2025-07-01", "split_ratio": 3})
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[3])
        self.assertDictEqual(result, {"split_date": "2025-04-01", "split_ratio": 5})
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[4])
        self.assertDictEqual(result, {"split_date": "2025-04-01", "split_ratio": 2})
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[5])
        self.assertDictEqual(result, {"split_date": "2024-10-01", "split_ratio": 2})
        result = self.reader.extract(Forecast).analyze_dividend_note_block(text_blocks[6])
        self.assertDictEqual(result, {"split_date": "2025-09-01", "split_ratio": 3})
