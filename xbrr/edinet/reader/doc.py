import os
import glob
from xbrr.base.reader.xbrl_doc import XbrlDoc

class Doc(XbrlDoc):

    def __init__(self, root_dir="", xbrl_kind=""):

        def _xbrl_file(root_dir, kind):
            folder_dict = {'public': 'XBRL/PublicDoc', 'audit': 'XBRL/AuditDoc'}
            xbrl_files = glob.glob(os.path.join(root_dir, folder_dict[kind]+"/*.xbrl"))
            if not os.path.isfile(xbrl_files[0]):
                raise Exception(
                    f"XBRL file does not exist.")
            return xbrl_files[0]

        xbrl_file=_xbrl_file(root_dir, xbrl_kind)
        self.file_spec = os.path.splitext(xbrl_file)[0]
        super().__init__("edinet", root_dir=root_dir, xbrl_file=xbrl_file)

    def find_path(self, kind):
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
        elif kind in suffix:
            path = self.file_spec + suffix[kind]
        else: # kind=file name case
            path = os.path.join(os.path.dirname(self.file_spec), kind)

        return path
