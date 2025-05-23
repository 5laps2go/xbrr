import os
import datetime
import unittest
from xbrr.tdnet.reader.doc import Doc


class TestDoc(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        cls.root_dir = os.path.join(_dir, "E24982")
        cls.ixbrl_dir = os.path.join(_dir, "081220210818487667")

    @classmethod
    def tearDownClass(cls):
        pass

    def test_doc(self):
        doc = Doc(root_dir=self.root_dir, xbrl_kind="public")

        self.assertEqual(doc.published_date[0], datetime.datetime(2021, 7, 14, 0, 0))
        self.assertEqual(doc.published_date[1], 'a')
        self.assertEqual(doc.company_code, '36450')

        self.assertGreater(len(doc.xsd.find_all("element")), 0)

    def test_read_ixbrl(self):
        doc = Doc(root_dir=self.ixbrl_dir, xbrl_kind="summary")

        bs = doc.read_ixbrl_as_xbrl()
        xbrl = bs.find('xbrli:xbrl')
        self.assertEqual(len(xbrl.attrs), 12)
        self.assertEqual(len(list(xbrl.find_all('context'))), 37)
        self.assertEqual(len(xbrl.contents), 221)
        # self.assertEqual(len(xbrl.contents), 153) # when xsi:nil element is skipped

    def test_read_manifest_ixbrl(self):
        doc = Doc(root_dir=self.ixbrl_dir, xbrl_kind="public")

        bs = doc.read_ixbrl_as_xbrl()
        xbrl = bs.find('xbrli:xbrl')
        self.assertEqual(len(xbrl.attrs), 9)
        self.assertEqual(len(list(xbrl.find_all('context'))), 5)
        self.assertEqual(len(list(xbrl.find_all('unit'))), 2)
        self.assertEqual(len(xbrl.contents), 187)
        # self.assertEqual(len(xbrl.contents), 169) # when xsi:nil element is skipped
