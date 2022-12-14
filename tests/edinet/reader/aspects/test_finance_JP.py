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
        # JP accounting standard: S100LU0G NISSAN, S100LLT7 出光興産
        root_dir = client.get_xbrl("S100LU0G", save_dir=_dir,
                                    expand_level="dir")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_accounting_standards(self):
        feature = self.reader.extract(Finance).accounting_standards
        self.assertEqual(feature.normalized_text, "Japan GAAP")

    def test_segment_information_by_EDINET(self):
        feature = self.reader.extract(Finance).segment_information
        self.assertTrue(feature.normalized_text.startswith("(セグメント情報等)"))
        self.assertEqual(feature.label, "セグメント情報等")
        self.assertEqual(feature.context, "CurrentYearDuration")

    def test_bs(self):
        bs = self.reader.extract(Finance).bs()
        self.assertTrue(bs is not None)
        # bs.to_csv(os.path.join(self._dir, 'test_bs.csv'))
        self.assertGreater(len(bs), 0)

    def test_pl(self):
        pl = self.reader.extract(Finance).pl()
        self.assertTrue(pl is not None)
        # pl.to_csv(os.path.join(self._dir, 'test_pl.csv'))
        self.assertGreater(len(pl), 0)

    def test_cf(self):
        cf = self.reader.extract(Finance).cf()
        # cf.to_csv(os.path.join(self._dir, 'test_cf.csv'))
        self.assertGreater(len(cf), 0)
