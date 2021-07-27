import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.edinet.reader.doc import Doc


class TestDoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = os.path.join(os.path.dirname(__file__), "../data")
        client = DocumentClient()
        cls.root_dir = client.get_xbrl("S100FGR9", save_dir=cls._dir,
                                    expand_level="dir")
        cls.doc = Doc(root_dir=cls.root_dir, xbrl_kind="public")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root_dir)

    def test_doc(self):
        doc = self.doc

        self.assertGreater(len(doc.xsd.find_all("element")), 0)
        self.assertGreater(len(doc.cal.find_all("calculationLink")), 0)
        self.assertGreater(len(doc.def_.find_all("definitionArc")), 0)
        self.assertGreater(len(doc.lab.find_all("labelLink")), 0)
        self.assertGreater(len(doc.lab_en.find_all("labelLink")), 0)
        self.assertGreater(len(doc.pre.find_all("presentationLink")), 0)
        self.assertTrue(doc.man.find("manifest"))

    def test_find_xsduri(self):
        doc = self.doc
        self.assertEqual(doc.find_xsduri("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor"),
                        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor_2018-02-28.xsd")

        self.assertEqual(doc.find_xsduri("http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E01726-000/2018-12-31/01/2019-03-27"),
                        "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd")
        self.assertEqual(doc.find_xsduri("local"),
                        "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd")

    def test_find_xmluri_xsd(self):
        doc = self.doc
        self.assertEqual(doc.find_xmluri('xsd', doc.find_xsduri("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor")),
                        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor_2018-02-28.xsd")

    def test_find_xmluri_lab(self):
        doc = self.doc
        self.assertEqual(doc.find_xmluri('lab', 'local'), "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27_lab.xml")
        self.assertEqual(doc.find_xmluri('lab', 'jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd'), "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27_lab.xml")

        self.assertEqual(doc.find_xmluri('lab', doc.find_xsduri('http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor')), 
                        "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/label/jpcrp_2018-02-28_lab.xml")
