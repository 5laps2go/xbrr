import os
import unittest
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.aspects.information import Information
import tests.edinet.reader.doc as testdoc


class TestInformation(unittest.TestCase):

    def get_xbrl(self):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        path = os.path.join(os.path.dirname(__file__),
                            "../../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=_dir)
        return xbrl

    def test_shareholders(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).shareholders
        self.assertTrue(feature.normalized_text.startswith("(5)【所有者別状況】"))

    def test_dividend_policy(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).dividend_policy
        self.assertTrue(feature.normalized_text.startswith("3【配当政策】"))

    def test_directors(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).directors
        self.assertTrue(feature.normalized_text.startswith("5【役員の状況】"))

    def test_corporate_governance(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).corporate_governance
        self.assertTrue(feature.normalized_text.startswith("(1)【コーポレート・ガバナンスの状況】"))

    def test_number_of_executives(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).number_of_directors
        self.assertEqual(feature.value, 14)

    def test_number_of_female_executives(self):
        xbrl = self.get_xbrl()
        feature = xbrl.extract(Information).number_of_female_executives
        self.assertEqual(feature.value, 1)
