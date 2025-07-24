import os
import shutil
import time
import unittest

import xbrr
from tests.utils import delay
from xbrr.edinet.reader.doc import Doc


class TestAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _dir = os.path.join(os.path.dirname(__file__), "data")
        # S100DE5C : TIS Inc. 2018-06-27 report
        cls.xbrl_doc = Doc(root_dir=os.path.join(_dir, "S100DE5C"), xbrl_kind="public")

    @classmethod
    def tearDownClass(cls):
        external = "external"
        if os.path.exists(external):
            shutil.rmtree(external)

    @delay
    def test_api_metadata(self):
        metadata = xbrr.edinet.api.metadata.get("2025-01-31")
        self.assertGreater(metadata.count, 0)

    @delay
    def test_api_document(self):
        _dir = os.path.dirname(__file__)
        path = xbrr.edinet.api.document.get_pdf("S100VH69", save_dir=_dir)
        self.assertTrue(os.path.exists(path))
        os.remove(path)

    @delay
    def test_api_documents(self):
        documents = xbrr.edinet.api.documents.get("2025-01-31")
        self.assertEqual(documents.metadata.count, len(documents.list))

        _dir = os.path.dirname(__file__)
        d = documents.list[0]
        for ext in ["xbrl", "pdf"]:
            time.sleep(3)
            if ext == "xbrl":
                path = d.get_xbrl(save_dir=_dir)
            else:
                path = d.get_pdf(save_dir=_dir)

            self.assertTrue(os.path.exists(path))
            os.remove(path)

    def test_extract(self):
        result = xbrr.reader.read(self.xbrl_doc).extract(
                    xbrr.edinet.aspects.Business).policy_environment_issue_etc
        self.assertTrue(result.value)
        self.assertEqual(result.name, 'BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock')
        self.assertEqual(result.data_type, 'textBlock')

    def test_extract_element(self):
        result = xbrr.reader.read(self.xbrl_doc).extract("information", "number_of_directors")
        self.assertEqual(result, 14)
