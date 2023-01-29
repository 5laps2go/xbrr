import os
import unittest
from xbrr.tdnet.reader.taxonomy import Taxonomy


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

        v = taxonomy.identify_version("http://www.xbrl.tdnet.info/taxonomy/jp/tse/tdnet/ed/t/2014-01-12")
        self.assertEqual(v, "2014-01-12")
