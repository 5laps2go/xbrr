import os
import unittest
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.aspects.metadata import Metadata
import tests.edinet.reader.doc as testdoc


class TestMetadata(unittest.TestCase):

    def get_xbrl(self):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        path = os.path.join(os.path.dirname(__file__),
                            "../../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=_dir)

        return xbrl

    def test_fiscal_year(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).fiscal_year
        self.assertEqual(feature.value, 2017)

    def test_fiscal_period_kind(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).fiscal_period_kind
        self.assertEqual(feature.value, "FY")

    def test_company_name(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).company_name
        self.assertEqual(feature.normalized_text, "TIS株式会社")

    def test_company_name_en(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).company_name_en
        self.assertEqual(feature.normalized_text, "TIS Inc.")

    def test_address(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).address
        self.assertEqual(feature.normalized_text, "東京都新宿区西新宿八丁目17番1号")

    def test_phone_number(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Metadata).phone_number
        self.assertEqual(feature.value, "03-5337-7070")
