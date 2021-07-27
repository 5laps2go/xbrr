import os
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

        self.assertGreater(len(doc.xsd.find_all("element")), 0)
        self.assertGreater(len(doc.cal.find_all("calculationLink")), 0)
        self.assertGreater(len(doc.def_.find_all("definitionArc")), 0)
        self.assertGreater(len(doc.lab.find_all("labelLink")), 0)
        self.assertGreater(len(doc.lab_en.find_all("labelLink")), 0)
        self.assertGreater(len(doc.pre.find_all("presentationLink")), 0)
        self.assertTrue(doc.man.find("manifest"))