import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.edinet.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc
import tests.edinet.reader.doc as testdoc
from xbrr.edinet.reader.aspects.finance import Finance


class TestFinance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        client = DocumentClient()
        # IFRS accounting standard: S100LO6W TOYOTA, S100LN4K 味の素, S100LJZ3 アイシン
        root_dir = client.get_xbrl("S100LO6W", save_dir=_dir,
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
        self.assertEqual(feature.normalized_text, "IFRS")

    def test_segment_information_by_EDINET(self):
        feature = self.reader.extract(Finance).segment_information
        self.assertIsNone(feature.value)
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
        cf = self.reader.extract(Finance).cf()
        # cf.to_csv(os.path.join(self._dir, 'test_cf.csv'))
        self.assertGreater(len(cf), 0)
