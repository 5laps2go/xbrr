import os
import shutil
import unittest
from xbrr.tdnet.client.document_client import DocumentClient
from xbrr.edinet.reader.reader import Reader
from xbrr.tdnet.reader.doc import Doc
import pandas as pd
from pandas.testing import assert_frame_equal


class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        client = DocumentClient()
        # "081220210719468981"Ｊ－日本ラッド １四半期決算短信〔日本基準〕"
        # "081220210803477803" 日鉄鉱 	2022年3月期 第1四半期決算短信〔日本基準〕（連結）
        root_dir = client.get_xbrl("081220210803477803", save_dir=_dir,
                                   expand_level="dir")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="summary")
        cls.reader = Reader(xbrl_doc, save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.reader.taxonomies_root):
            shutil.rmtree(cls.reader.taxonomies_root)

    def test_roles(self):
        roles = self.reader.roles
        self.assertTrue(len(roles) > 0)
        for k,v in roles.items():
            print(v.label, k)

    def test_namespaces(self):
        namespaces = self.reader.namespaces
        self.assertTrue(len(namespaces) > 0)

    def test_read_value_by_role(self):
        # roles in summary
        #   RoleBusinessResultsQuarterlyOperatingResults    四半期経営成績
        #   RoleBusinessResultsQuarterlyFinancialPositions  四半期財政状態
        #   RoleQuarterlyForecasts                          四半期業績予想
        fc_role = self.reader.find_role_name('fc')
        bro = self.reader.read_value_by_role(fc_role)
        bro.to_csv(os.path.join(self._dir, 'test_bro.csv'))
        self.assertGreater(len(bro), 0)
