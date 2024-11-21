import os
import shutil
import unittest
from xbrr.xbrl.reader.taxonomy_repository import TaxonomyRepository
from datetime import datetime

class TestTaxonomyRepository(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        cls.repository = TaxonomyRepository(save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.repository.taxonomies_root):
            shutil.rmtree(cls.repository.taxonomies_root)

    def test_load_schema_files_tdnet(self):
        nsdecls = {
            'jppfs_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2020-11-01/jppfs_cor",
            'ixt':"http://www.xbrl.org/inlineXBRL/transformation/2011-07-31",
            'tse-acedjpfr-36450':"http://www.xbrl.tdnet.info/jp/tse/tdnet/ac/edjp/fr/36450/2021-05-31/01/2021-07-14",
            'brli':"http://www.xbrl.org/2003/instance",
            'jpdei_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor",
            'xbrldt':"http://xbrl.org/2005/xbrldt",
            'xbrldi':"http://xbrl.org/2006/xbrldi",
            'link':"http://www.xbrl.org/2003/linkbase",
            'xsi':"http://www.w3.org/2001/XMLSchema-instance",
            'xlink':"http://www.w3.org/1999/xlink",
            'iso4217':"http://www.xbrl.org/2003/iso4217",
            'jpcrp_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2020-11-01/jpcrp_cor"
        }
        results = self.repository.load_schema_files(nsdecls)
        self.assertEqual(1, len(results.schema_dicts))
        self.assertIn('2020-11-01', results.schema_dicts)

    def tests_load_schema_files_edinet(self):
        nsdecls = {
            'link':"http://www.xbrl.org/2003/linkbase",
            'jpdei_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jpdei/2013-08-31/jpdei_cor",
            'jpcrp030000-asr_E05739-000':"http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E05739-000/2019-03-31/01/2019-06-26",
            'xbrldi':"http://xbrl.org/2006/xbrldi",
            'iso4217':"http://www.xbrl.org/2003/iso4217",
            'xsi':"http://www.w3.org/2001/XMLSchema-instance",
            'xlink':"http://www.w3.org/1999/xlink",
            'jpcrp_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-03-31/jpcrp_cor",
            'xbrli':"http://www.xbrl.org/2003/instance",
            'jppfs_cor':"http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2018-03-31/jppfs_cor"
        }
        results = self.repository.load_schema_files(nsdecls)
        self.assertEqual(1, len(results.schema_dicts))
        self.assertIn('2018-03-31', results.schema_dicts)

    def test_uri_to_path(self):
        result = self.repository.uri_to_path('http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2020-11-01/jpigp_cor_2020-11-01.xsd')
        self.assertTrue(result[0].endswith('external/taxonomy/edinet/jpigp/2020-11-01/jpigp_cor_2020-11-01.xsd'))
