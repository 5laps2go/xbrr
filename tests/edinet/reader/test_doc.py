import os
import shutil
import unittest
from datetime import datetime

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

        self.assertEqual(doc.published_date[0], datetime(2019, 3, 27, 0, 0))
        self.assertEqual(doc.published_date[1], 'a')
        self.assertEqual(doc.company_code, 'E01726')

        self.assertGreater(len(doc.xsd.find_all("element")), 0)

    # def test_find_xsduri(self):
    #     doc = self.doc
    #     self.assertEqual(doc.find_xsduri("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor"),
    #                     "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor_2018-02-28.xsd")

    #     self.assertEqual(doc.find_xsduri("http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E01726-000/2018-12-31/01/2019-03-27"),
    #                     "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd")
    #     self.assertEqual(doc.find_xsduri("local"),
    #                     "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd")

    # def test_find_laburi(self):
    #     doc = self.doc
    #     self.assertEqual(doc.find_kind_uri('lab', ''), "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27_lab.xml")
    #     self.assertEqual(doc.find_kind_uri('lab', 'jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27.xsd'), "jpcrp030000-asr-001_E01726-000_2018-12-31_01_2019-03-27_lab.xml")

    #     self.assertEqual(doc.find_kind_uri('lab', doc.find_xsduri('http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor')), 
    #                     "http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/label/jpcrp_2018-02-28_lab.xml")
