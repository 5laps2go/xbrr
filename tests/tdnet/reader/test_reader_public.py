import os
import shutil
import unittest
from xbrr.tdnet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.tdnet.reader.doc import Doc
import pandas as pd

class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        client = DocumentClient()
        # "081220210818487667" Ｊ－共和工業 2022年4月期 第1四半期決算短信〔日本基準〕（連結）
        # root_dir = client.get_xbrl("081220210818487667", save_dir=_dir,
        #                            expand_level="dir")
        root_dir = os.path.join(_dir, "081220210818487667")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        # shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomy_repo.taxonomies_root)

    def test_custom_roles(self):
        roles = self.reader.custom_roles
        self.assertTrue(len(roles) > 0)
        self.assertIn('rol_QuarterlyConsolidatedBalanceSheet', roles)               # 310030 四半期連結貸借対照表
        self.assertIn('rol_YearToQuarterEndConsolidatedStatementOfComprehensiveIncome', roles)  # 322031 四半期連結包括利益計算書　四半期連結累計期間
        self.assertIn('rol_YearToQuarterEndConsolidatedStatementOfIncome', roles)   # 321031 四半期連結損益（及び包括利益）計算書　四半期連結累計期間
        self.assertIn('RoleAttachedDocument', roles)
        # for k,v in roles.items():
        #     print(v.label, k)

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertTrue(len(namespaces) > 0)
        self.assertIn('jpdei_cor', namespaces)
        self.assertIn('jppfs_cor', namespaces)
        self.assertIn('jpcrp_cor', namespaces)
        # self.assertIn('tse-qcedjpfr-15150', namespaces)

    def test_read_value_by_role(self):
        # rol_QuarterlyConsolidatedBalanceSheet                             310030 四半期連結貸借対照表                                
        bro = self.reader.read_value_by_role('rol_YearToQuarterEndConsolidatedStatementOfIncome')
        # bro.to_csv(os.path.join(self._dir, 'test_bro.csv'))
        assert bro is not None
        self.assertGreater(len(bro), 0)
