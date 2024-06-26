import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc
import tests.edinet.reader.doc as testdoc
import pandas as pd
from pandas.testing import assert_frame_equal


class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        client = DocumentClient()
        # S100DDYF 味の素 based on IFRS accounting standard, but no IFRS related roles are found.
        root_dir = client.get_xbrl("S100DDYF", save_dir=_dir,
                                    expand_level="dir")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_findv(self):
        path = os.path.join(os.path.dirname(__file__),
                            "../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=self._dir)
        element_value = xbrl.findv("jpdei_cor:EDINETCodeDEI")
        self.assertEqual(element_value.value, "E05739")

    def test_to_html(self):
        path = os.path.join(os.path.dirname(__file__),
                            "../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=self._dir)
        tag = "jpcrp_cor:InformationAboutOfficersTextBlock"
        html = xbrl.findv(tag).html

        self.assertTrue(html)

    def test_get_element(self):
        path = os.path.join(os.path.dirname(__file__),
                            "../data/xbrl2019.xbrl")
        xbrl = Reader(testdoc.Doc(path), save_dir=self._dir)
        element_value = xbrl.findv("jpcrp_cor:NumberOfEmployees")
        self.assertEqual(element_value.value, "19081")
        self.assertEqual(element_value.decimals, "0")

        self.assertDictEqual(element_value.to_dict(), {
            'name': 'NumberOfEmployees', 
            'reference': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor#jpcrp_cor_NumberOfEmployees',
            'value': '19081', 'unit': 'pure', 'decimals': '0', 'consolidated': True, 
            'context': 'Prior4YearInstant', 'member': '', 'period': '2014-03-31', 'period_start': None, 'label': ''})

    # def test_taxonomy_year(self):
    #     self.assertEqual(self.reader.taxonomy_year, ["2018", "2014"])

    def test_custom_roles(self):
        roles = self.reader.custom_roles
        self.assertEqual(len(roles), 12)
        self.assertTrue("rol_BalanceSheet" in roles)
        self.assertTrue("rol_StatementOfIncome" in roles)

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertEqual(len(namespaces), 10)
        self.assertFalse("jpigp_cor" in namespaces) # true means IFRS accounting standard

    def test_get_schema_by_link(self):
        taxonomy_element = self.reader.get_schema_by_link("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor_2018-02-28.xsd#jpcrp_cor_AnnexedDetailedScheduleOfProvisionsTextBlock")
        local_element = self.reader.get_schema_by_link("jpcrp030000-asr-001_E00436-000_2018-03-31_01_2018-06-26.xsd#jpcrp030000-asr_E00436-000_ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsHeading")
        self.assertTrue(taxonomy_element)
        self.assertEqual(taxonomy_element.label, "引当金明細表")
        self.assertTrue(local_element)
        self.assertTrue(local_element.label, "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析")

    def test_read_schema_by_role(self):
        bs = self.reader.read_schema_by_role("rol_BalanceSheet").reset_index()
        bs = bs[[x for x in bs.dtypes.keys() if bs.dtypes[x]==object]] # drop implementation specific columns
        self.assertGreater(len(bs), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DDYF-bs.csv"),index_col=0,dtype=bs.dtypes.apply(lambda x: {'object':str,'int64':int,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        assert_frame_equal(bs, expected_df)

    def test_read_value_by_role(self):
        pl = self.reader.read_value_by_role("rol_StatementOfIncome")
        pl = pl[[x for x in pl.dtypes.keys() if pl.dtypes[x]==object]] # drop implementation specific columns
        self.assertGreater(len(pl), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DDYF-pl.csv"),index_col=0,dtype=pl.dtypes.apply(lambda x: {'object':str,'int64':int,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        assert_frame_equal(pl, expected_df)

    def test_read_current_value_by_role(self):
        pl = self.reader.read_value_by_role("rol_StatementOfIncome", scope='Current')
        pl = pl[[x for x in pl.dtypes.keys() if pl.dtypes[x]==object]] # drop implementation specific columns
        self.assertGreater(len(pl), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DDYF-pl.csv"),index_col=0,dtype=pl.dtypes.apply(lambda x: {'object':str,'int64':int,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        expected_df = expected_df.loc[expected_df['context'].str.startswith('Current')].reset_index(drop=True)
        assert_frame_equal(pl, expected_df)
