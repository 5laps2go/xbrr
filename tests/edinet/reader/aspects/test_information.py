import os
import shutil
import unittest

from xbrr.edinet.reader.doc import Doc
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.aspects.information import Information


class TestInformation(unittest.TestCase):

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

    def test_shareholders(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).shareholders
        self.assertTrue(feature.normalized_text.startswith("(5)【所有者別状況】"))

    def test_dividend_policy(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).dividend_policy
        self.assertTrue(feature.normalized_text.startswith("3【配当政策】"))

    def test_directors(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).directors
        self.assertTrue(feature.normalized_text.startswith("5【役員の状況】"))

    def test_corporate_governance(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).corporate_governance
        self.assertTrue(feature.normalized_text.startswith("(1)【コーポレート・ガバナンスの状況】"))

    def test_number_of_executives(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).number_of_directors
        self.assertEqual(feature, 14)

    def test_number_of_female_executives(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Information).number_of_female_executives
        self.assertEqual(feature, 1)
