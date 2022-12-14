import os
import shutil
import unittest
from xbrr.xbrl.reader.reader import Reader
from xbrr.tdnet.reader.doc import Doc
from xbrr.xbrl.reader.taxonomy_repository import TaxonomyRepository


class TestReader(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "../data")
        cls.taxonomy_repo = TaxonomyRepository(save_dir=_dir)
        cls._dir = _dir

    @classmethod
    def tearDownClass(cls):
        pass
        # shutil.rmtree(cls.reader.xbrl_doc.root_dir)
        if os.path.exists(cls.taxonomy_repo.taxonomies_root):
            shutil.rmtree(cls.taxonomy_repo.taxonomies_root)

    def test_xsd_dic(self):
        # "081220210818487667" Ｊ－共和工業 2022年4月期 第1四半期決算短信〔日本基準〕（連結）
        # root_dir = client.get_xbrl("081220210818487667", save_dir=_dir,
        #                            expand_level="dir")
        root_dir = os.path.join(self._dir, "081220210818487667")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        reader = Reader(xbrl_doc, self.taxonomy_repo, save_dir=self._dir)

        bs = reader.read_schema_by_role("rol_QuarterlyConsolidatedBalanceSheet").reset_index()
        xsd_dic1 = self.taxonomy_repo.taxonomy_repo
        # print(self.taxonomy_repo.taxonomy_repo['2021']['jppfs_cor_AssetsAbstract'])
        download_state = self.taxonomy_repo.download_state

        root_dir = os.path.join(self._dir, "E24982")
        xbrl_doc = Doc(root_dir=root_dir, xbrl_kind="public")
        reader = Reader(xbrl_doc, self.taxonomy_repo, save_dir=self._dir)

        bs = reader.read_schema_by_role("rol_BalanceSheet").reset_index()
        xsd_dic2 = self.taxonomy_repo.taxonomy_repo
        # print(self.taxonomy_repo.taxonomy_repo['2021']['jppfs_cor_AssetsAbstract'])

        self.assertDictEqual(download_state, self.taxonomy_repo.download_state)
        self.assertDictEqual(xsd_dic1, xsd_dic2)