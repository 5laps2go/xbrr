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
        if os.path.exists(cls.reader.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomies_root)

    def test_accounting_standards(self):
        feature = self.reader.extract(Forecast).accounting_standards
        self.assertEqual(feature, "日本基準")
        feature = self.reader.extract(Forecast).consolidated
        self.assertTrue(feature)

    def test_fiscal_period_kind(self):
        feature = self.reader.extract(Forecast).fiscal_period_kind
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
