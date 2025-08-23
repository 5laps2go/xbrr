import os
import shutil
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
from pandas.api.types import is_numeric_dtype, is_string_dtype, is_bool_dtype, is_object_dtype

from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc


class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        # S100DE5C : TIS Inc. 2018-06-27 report
        xbrl_doc = Doc(root_dir=os.path.join(_dir, "S100DE5C"), xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_findv(self):
        element_value = self.reader.findv("jpdei_cor:EDINETCodeDEI")
        assert element_value is not None
        self.assertEqual(element_value.value, "E05739")

    def test_to_html(self):
        tag = "jpcrp_cor:InformationAboutOfficersTextBlock"
        element_value = self.reader.findv(tag)
        assert element_value is not None
        html = element_value.html
        self.assertTrue(html)

    def test_get_element(self):
        element_value = self.reader.findv("jpcrp_cor:NumberOfEmployees")
        assert element_value is not None
        self.assertEqual(element_value.value, "19081")
        self.assertEqual(element_value.decimals, "0")

        self.assertDictEqual(element_value.to_dict(), {
            'name': 'NumberOfEmployees', 
            'reference': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor#jpcrp_cor_NumberOfEmployees',
            'value': '19081', 'unit': 'pure', 'decimals': '0', 'consolidated': True, 
            'context': 'Prior4YearInstant', 'member': '', 'period': '2014-03-31', 'period_start': None, 'label': '従業員数', 'dimension':''})

    def test_taxonomy_repository(self):
        self.assertIn('2018-02-28', self.reader.schema_dic.schema_dicts)
        self.assertIn('2013-08-31', self.reader.schema_dic.schema_dicts)


    def test_custom_roles(self):
        roles = self.reader.custom_roles
        self.assertEqual(len(roles), 29)
        self.assertTrue("rol_BalanceSheet" in roles)
        self.assertTrue("rol_StatementOfIncome" in roles)

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertEqual(len(namespaces), 10)
        self.assertFalse("jpigp_cor" in namespaces) # true means IFRS accounting standard

    def test_get_schema_by_link(self):
        taxonomy_element = self.reader.get_schema_by_link("http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2018-02-28/jpcrp_cor_2018-02-28.xsd#jpcrp_cor_AnnexedDetailedScheduleOfProvisionsTextBlock")
        local_element = self.reader.get_schema_by_link("jpcrp030000-asr-001_E05739-000_2018-03-31_01_2018-06-27.xsd#jpcrp030000-asr_E05739-000_ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsHeading")
        self.assertTrue(taxonomy_element)
        self.assertEqual(taxonomy_element.label, "引当金明細表")
        self.assertTrue(local_element)
        self.assertTrue(local_element.label, "経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析")

    def test_read_schema_by_role(self):
        bs = self.reader.read_schema_by_role(self.reader.custom_roles["rol_BalanceSheet"].uri).reset_index()
        bs = bs[[x for x in bs.columns if is_object_dtype(bs[x])]] # drop implementation specific columns
        self.assertGreater(len(bs), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DE5C-bs.csv"),index_col=0,dtype=bs.dtypes.apply(lambda x: {'object':str,'int64':int,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        assert_frame_equal(bs, expected_df)

    def test_read_value_by_role(self):
        pl = self.reader.read_value_by_role(self.reader.custom_roles["rol_StatementOfIncome"].uri)
        assert pl is not None
        self.assertGreater(len(pl), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DE5C-pl.csv"),index_col=0,dtype=pl.dtypes.apply(lambda x: {'object':str,'int64':int,'float64':float,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        assert_frame_equal(pl, expected_df)

    def test_read_current_value_by_role(self):
        pl = self.reader.read_value_by_role(self.reader.custom_roles["rol_StatementOfIncome"].uri, scope='Current')
        assert pl is not None
        self.assertGreater(len(pl), 0)
        expected_df = pd.read_csv(os.path.join(os.path.dirname(__file__), "../data/S100DE5C-pl.csv"),index_col=0,dtype=pl.dtypes.apply(lambda x: {'object':str,'int64':int,'float64':float,'bool':bool}[x.name]).to_dict(),keep_default_na=False)
        expected_df = expected_df.loc[expected_df['context'].str.startswith('Current')].reset_index(drop=True)
        assert_frame_equal(pl, expected_df)
