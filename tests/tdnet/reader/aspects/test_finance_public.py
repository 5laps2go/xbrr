import os
import shutil
import unittest
from xbrr.tdnet.client.document_client import DocumentClient
from xbrr.edinet.reader.reader import Reader
from xbrr.tdnet.reader.doc import Doc
from xbrr.tdnet.reader.aspects.finance import Finance


class TestFinancePublic(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        client = DocumentClient()
        # "081220210719468981"Ｊ－日本ラッド １四半期決算短信〔日本基準〕"
        # "081220210803477803" 日鉄鉱 	2022年3月期 第1四半期決算短信〔日本基準〕（連結）
        root_dir = client.get_xbrl("081220210803477803", save_dir=_dir,
                                   expand_level="dir")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomies_root)

    def test_accounting_standards(self):
        feature = self.reader.extract(Finance).accounting_standards
        self.assertEqual(feature.normalized_text, "Japan GAAP")

    def test_fiscal_period_kind(self):
        feature = self.reader.extract(Finance).fiscal_period_kind
        self.assertEqual(feature.normalized_text, "Q1")

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertTrue(len(namespaces) > 0)
        self.assertIn('jpdei_cor', namespaces)
        self.assertIn('jppfs_cor', namespaces)
        self.assertIn('jpcrp_cor', namespaces)
        self.assertIn('tse-qcedjpfr-15150', namespaces)

    def test_segment_information_by_EDINET(self):
        feature = self.reader.extract(Finance).segment_information
        self.assertIsNone(feature)
        # self.assertTrue(feature.normalized_text.startswith("(セグメント情報等)"))
        # self.assertEqual(feature.label, "セグメント情報等")
        # self.assertEqual(feature.context, "CurrentYearDuration")

    def test_bs(self):
        bs = self.reader.extract(Finance).bs()
        self.assertTrue(bs is not None)
        self.assertGreater(len(bs), 0)

    def test_pl(self):
        pl = self.reader.extract(Finance).pl()
        self.assertTrue(pl is not None)
        self.assertGreater(len(pl), 0)

    def test_cf(self):
        if self.reader.extract(Finance).fiscal_period_kind == 'ALL':
            cf = self.reader.extract(Finance).cf()
            if type(cf) is not list:
                self.assertGreater(len(cf), 0)
            else:
                self.assertGreater(len(cf), 0)
