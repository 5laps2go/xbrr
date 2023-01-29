import os
import datetime
import unittest
from xbrr.tdnet.reader.doc import Doc


class TestDoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        cls.root_dir = os.path.join(_dir, "E24982")

    @classmethod
    def tearDownClass(cls):
        pass

    def test_doc(self):
        doc = Doc(root_dir=self.root_dir, xbrl_kind="public")

        self.assertEqual(doc.published_date[0], datetime.datetime(2021, 7, 14, 0, 0))
        self.assertEqual(doc.published_date[1], 'a')
        self.assertEqual(doc.company_code, '36450')

        self.assertGreater(len(doc.xsd.find_all("element")), 0)
