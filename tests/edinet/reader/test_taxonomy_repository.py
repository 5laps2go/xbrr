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

    def test_get_family_versions(self):
        results = self.repository.get_family_versions(datetime(2021,6,8))
        self.assertEqual(['edinet:2021', 'tdnet:2014'], results)

    def test_get_schema_dict(self):
        results = self.repository.get_schema_dict(['edinet:2021', 'tdnet:2014'])
        self.assertEqual({}, results)
        self.assertEqual({}, self.repository.taxonomy_repo['2021'])
        self.assertFalse(self.repository.download_state['edinet:2021'])
        self.assertFalse(self.repository.download_state['tdnet:2014'])

    def test_provision(self):
        results = self.repository.provision(
            'http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2020-11-01/jpigp_cor_2020-11-01.xsd',
            ['edinet:2021', 'tdnet:2014'])
        self.assertTrue(os.path.join(self._dir, "external/taxonomy/2021"))
        self.assertTrue(os.path.join(self._dir, "external/taxonomy/edinet/jpcrp"))

    def test_uri_to_path(self):
        result = self.repository.uri_to_path('http://disclosure.edinet-fsa.go.jp/taxonomy/jpigp/2020-11-01/jpigp_cor_2020-11-01.xsd')
        self.assertTrue(os.path.exists(result[0]))
