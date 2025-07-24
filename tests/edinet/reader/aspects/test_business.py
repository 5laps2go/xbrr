import os
import shutil
import unittest
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.edinet.reader.doc import Doc
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.aspects.business import Business


class TestBusiness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../../data")
        # S100DE5C : TIS Inc. 2018-06-27 report
        xbrl_doc = Doc(root_dir=os.path.join(_dir, "S100DE5C"), xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_policy_environment_issue_etc(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Business).policy_environment_issue_etc
        self.assertTrue(feature.normalized_text.startswith("1【経営方針、経営環境及び対処すべき課題等】"))

    def test_risks(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Business).risks
        self.assertTrue(feature.normalized_text.startswith("2【事業等のリスク】"))

    def test_management_analysis(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Business).management_analysis
        self.assertTrue(feature.normalized_text.startswith("3【経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析】"))

    def test_research_and_development(self):
        # xbrl = self.get_xbrl()
        feature = self.reader.extract(Business).research_and_development
        self.assertTrue(feature.normalized_text.startswith("5【研究開発活動】"))
