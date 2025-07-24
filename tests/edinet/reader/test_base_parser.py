import os
import re
import shutil
import unittest
from xbrr.edinet.reader.doc import Doc
from xbrr.xbrl.reader.reader import Reader
from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class TestBaseParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        # S100DE5C : TIS Inc. 2018-06-27 report
        xbrl_doc = Doc(root_dir=os.path.join(_dir, "S100DE5C"), xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)


    def test_search_text(self):
        tag = "jpcrp_cor:InformationAboutOfficersTextBlock"
        parser = BaseParser(self.reader, ElementValue, {
            "test": tag
        })
        pattern = "^(男性).+(名).+(女性).+(名)"
        text = parser.search("test", pattern)
        self.assertEqual(text, "男性 13名 女性 1名 (役員のうち女性の比率 7.1%)")

    def test_extract_value(self):
        tag = "jpcrp_cor:InformationAboutOfficersTextBlock"
        parser = BaseParser(self.reader, ElementValue, {
            "test": tag
        })
        pattern = "^(男性).+(名).+(女性).+(名)"
        for p, s in [("男性", "名"), ("女性", "名"), ("女性の比率", "%")]:
            value = parser.extract_value("test", p, s, filter_pattern=pattern)
            if p == "男性":
                self.assertEqual(value, 13)
            elif p == "女性":
                self.assertEqual(value, 1)
            else:
                self.assertEqual(value, 7.1)
