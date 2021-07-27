import os
import glob
from xbrr.base.reader.xbrl_doc import XbrlDoc

class Doc(XbrlDoc):

    def __init__(self, root_dir="", xbrl_kind=""):

        def _xbrl_file(root_dir, kind):
            folder_dict = {'public': 'XBRLData/Attachment', 'summary': 'XBRLData/Summary'}
            xbrl_files = glob.glob(os.path.join(root_dir, folder_dict[kind]+"/*.xbrl"))
            if not os.path.isfile(xbrl_files[0]):
                raise Exception(
                    f"XBRL file does not exist.")
            return xbrl_files[0]
        
        xbrl_file=_xbrl_file(root_dir, xbrl_kind)
        self.file_spec = os.path.splitext(xbrl_file)[0]
        super().__init__("tdnet", root_dir=root_dir, xbrl_file=xbrl_file)

    def find_path(self, kind):
        # TDNET report file name spec. is like EDINET
        suffix = {
            "xbrl": ".xbrl", "xsd": ".xsd", "cal": "-cal.xml", "def": "-def.xml",
            "lab": "-lab.xml", "lab-en": "-lab-en.xml", "pre": "-pre.xml",
            }

        if kind == "man":
            path = os.path.join(os.path.dirname(self.file_spec), "manifest.xml")
            if len(path)==0:
                return None
        elif kind in suffix:
            path = self.file_spec + suffix[kind]
        else: # kind=file name case
            path = os.path.join(os.path.dirname(self.file_spec), kind)

        return path
