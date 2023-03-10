import os
import shutil
import time
import unittest

import xbrr
from tests.utils import delay
from xbrr.tdnet.reader.doc import Doc


class TestAPI(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        external = "external"
        if os.path.exists(external):
            shutil.rmtree(external)

    @delay
    def test_api_document(self):
        _dir = os.path.dirname(__file__)
        path = xbrr.tdnet.api.document.get_pdf("140120230310528211", save_dir=_dir)
        self.assertTrue(os.path.exists(path))
        os.remove(path)

    @delay
    def test_api_documents(self):
        documents = xbrr.tdnet.api.documents.get("2023-03-10")
        self.assertEqual(documents.metadata.count, len(documents.list))

        _dir = os.path.dirname(__file__)
        d = documents.list[0]
        for ext in ["xbrl", "pdf"]:
            time.sleep(3)
            if ext == "xbrl":
                if not d.has_xbrl: continue
                path = d.get_xbrl(save_dir=_dir)
            else:
                if not d.has_pdf: continue
                path = d.get_pdf(save_dir=_dir)

            self.assertTrue(os.path.exists(path))
            os.remove(path)

    def test_extract(self):
        path = os.path.join(os.path.dirname(__file__),
                            "./data/081220210818487667")

        result = xbrr.reader.read(Doc(path, 'public')).extract(
                    xbrr.tdnet.aspects.Metadata).company_name
        self.assertTrue(result.value)

