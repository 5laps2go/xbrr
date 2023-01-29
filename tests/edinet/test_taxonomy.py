import os
import unittest
from xbrr.edinet.reader.taxonomy import Taxonomy


class TestTaxonomy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._dir = os.path.join(os.path.dirname(__file__), "../data")

    @classmethod
    def tearDownClass(cls):
        pass

    def test_doc(self):
        taxonomy = Taxonomy(self._dir)

        v = taxonomy.identify_version("http://www.xbrl.tdnet.info/jp/tse/tdnet/ac/edjp/fr/36450/2021-05-31/01/2021-07-14")
        self.assertEqual(v, '')

        v = taxonomy.identify_version("http://info.edinet-fsa.go.jp/jp/fr/gaap/o/rt/2013-03-01")
        self.assertEqual(v, "2013-03-01")

        v = taxonomy.identify_version("http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2019-11-01/jppfs_cor")
        self.assertEqual(v, "2019-11-01")
