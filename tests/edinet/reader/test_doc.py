import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.edinet.reader.doc import Doc


class TestDoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        client = DocumentClient()
        cls.root_dir = client.get_xbrl("S100FGR9", save_dir=_dir,
                                    expand_level="dir")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root_dir)

    def test_doc(self):
        doc = Doc(root_dir=self.root_dir, xbrl_kind="public")

        self.assertGreater(len(doc.xsd.find_all("element")), 0)
        self.assertGreater(len(doc.cal.find_all("calculationLink")), 0)
        self.assertGreater(len(doc.def_.find_all("definitionArc")), 0)
        self.assertGreater(len(doc.lab.find_all("labelLink")), 0)
        self.assertGreater(len(doc.lab_en.find_all("labelLink")), 0)
        self.assertGreater(len(doc.pre.find_all("presentationLink")), 0)
        self.assertTrue(doc.man.find("manifest"))
