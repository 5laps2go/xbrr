import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc
from xbrr.edinet.reader.aspects.stock import Stock


class TestStock(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        client = DocumentClient()
        root_dir = client.get_xbrl("S100G70J", save_dir=_dir,
                                    expand_level="dir")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.join(cls.reader.save_dir, "S100G70J"))
        if os.path.exists(cls.reader.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomies_root)

    def test_dividend_paid(self):
        feature = self.reader.extract(Stock).dividend_paid
        self.assertEqual(feature.label, "１株当たり配当額")
        self.assertEqual(feature.value, "30.00")

    def test_dividends_surplus(self):
        feature = self.reader.extract(Stock).dividends_surplus
        self.assertEqual(feature.label, "剰余金の配当")
        self.assertEqual(feature.value, "-3258000000")

    def test_purchase_treasury_stock(self):
        feature = self.reader.extract(Stock).purchase_treasury_stock
        self.assertEqual(feature.label, "自己株式の取得")
        self.assertEqual(feature.value, "-4914000000")
