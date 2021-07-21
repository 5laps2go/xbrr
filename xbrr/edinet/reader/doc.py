import os
import glob
from xbrr.base.reader.base_doc import BaseDoc
from bs4 import BeautifulSoup

class Doc(BaseDoc):

    def __init__(self, root_dir="", xbrl_kind=""):

        def _xbrl_file(root_dir, kind):
            folder_dict = {'public': 'XBRL/PublicDoc', 'audit': 'XBRL/AuditDoc'}
            xbrl_files = glob.glob(os.path.join(root_dir, folder_dict[kind]+"/*.xbrl"))
            if not os.path.isfile(xbrl_files[0]):
                raise Exception(
                    f"XBRL file does not exist.")
            return xbrl_files[0]

        super().__init__("edinet", root_dir=root_dir, xbrl_file=_xbrl_file(root_dir, xbrl_kind))
        self.file_spec = os.path.splitext(self.xbrl_file)[0]

    def _find_file(self, kind, as_xml=True):
        # EDINET report file name spec.: https://www.fsa.go.jp/search/20170228/2a_1.pdf (4-3)
        suffix = {
            "xbrl": ".xbrl", "xsd": ".xsd", "cal": "_cal.xml", "def": "_def.xml",
            "lab": "_lab.xml", "lab-en": "_lab-en.xml", "pre": "_pre.xml",
            }

        if kind == "man":
            manifest = glob.glob(os.path.join(os.path.dirname(self.file_spec), "manifest_*.xml"))
            if len(manifest)==0:
                return None
            path = manifest[0]
        else:
            path = self.file_spec + suffix[kind]
            if not os.path.isfile(path):
                return None

        if as_xml:
            xml = None
            with open(path, encoding="utf-8-sig") as f:
                xml = BeautifulSoup(f, "lxml-xml")
            return xml
        else:
            return path
