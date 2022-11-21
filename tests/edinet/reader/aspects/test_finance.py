import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc
import tests.edinet.reader.doc as testdoc
from xbrr.edinet.reader.aspects.finance import Finance


class TestFinance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        client = DocumentClient()
        root_dir = client.get_xbrl("S100LOZE", save_dir=_dir,
                                    expand_level="dir")
        xbrl_doc = Doc(root_dir=str(root_dir), xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomies_root)

    def get_xbrl(self):
        path = os.path.join(os.path.dirname(__file__),
                            "../../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=self._dir)
        return xbrl

    def test_voluntary_accounting_policy_change(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Finance).voluntary_accounting_policy_change
        self.assertEqual(feature.value, None)

    def test_segment_information(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Finance).segment_information
        self.assertTrue(feature.normalized_text.startswith("(セグメント情報等)"))
        self.assertEqual(feature.label, "")
        self.assertEqual(feature.context, "CurrentYearDuration")

    def test_real_estate_for_lease(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Finance).real_estate_for_lease
        self.assertEqual(feature.value, None)

    def test_segment_information_by_EDINET(self):
        feature = self.reader.extract(Finance).segment_information
        self.assertTrue(feature.normalized_text.startswith("(セグメント情報等)"))
        self.assertEqual(feature.label, "セグメント情報等")
        self.assertEqual(feature.context, "CurrentYearDuration")

    def test_bs(self):
        bs = self.reader.extract(Finance).bs()
        # bs.to_csv("bs.csv", index=False, encoding="shift_jis")
        self.assertTrue(bs is not None)
        self.assertGreater(len(bs), 0)

    def test_pl(self):
        pl = self.reader.extract(Finance).pl()
        # pl.to_csv("pl.csv", index=False, encoding="shift_jis")
        self.assertTrue(pl is not None)
        self.assertGreater(len(pl), 0)
