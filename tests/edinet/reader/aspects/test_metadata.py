import os
import shutil
import unittest

from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.aspects.metadata import Metadata
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc


class TestMetadata(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        # S100DE5C : TIS Inc. 2018-06-27 report
        xbrl_doc = Doc(root_dir=os.path.join(_dir, "S100DE5C"), xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_fiscal_year(self):
        feature = self.reader.extract(Metadata).fiscal_year
        self.assertEqual(feature, 2017)

    def test_fiscal_period_kind(self):
        feature = self.reader.extract(Metadata).fiscal_period_kind
        self.assertEqual(feature.value, "FY")

    def test_company_name(self):
        feature = self.reader.extract(Metadata).company_name
        self.assertEqual(feature.normalized_text, "TIS株式会社")

    def test_company_name_en(self):
        feature = self.reader.extract(Metadata).company_name_en
        self.assertEqual(feature.normalized_text, "TIS Inc.")

    def test_address(self):
        feature = self.reader.extract(Metadata).address
        self.assertEqual(feature.normalized_text, "東京都新宿区西新宿八丁目17番1号")

    def test_phone_number(self):
        feature = self.reader.extract(Metadata).phone_number
        self.assertEqual(feature.value, "03-5337-7070")
