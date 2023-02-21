import os
import glob
from datetime import datetime
from xbrr.base.reader.xbrl_doc import XbrlDoc
from xbrr.edinet.reader.taxonomy import Taxonomy as EdinetTaxonomy
from xbrr.base.reader.base_taxonomy import BaseTaxonomy

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

    def find_path(self, kind) -> str:
        # EDINET report file name spec.: https://www.fsa.go.jp/search/20170228/2a_1.pdf (4-3)
        suffix = {
            "xbrl": ".xbrl", "xsd": ".xsd",
            # "cal": "_cal.xml", "def": "_def.xml",
            # "lab": "_lab.xml", "lab-en": "_lab-en.xml", "pre": "_pre.xml",
            }

        if kind == "man":
            manifest = glob.glob(os.path.join(os.path.dirname(self.file_spec), "manifest_*.xml"))
            if len(manifest)==0:
                raise Exception(f"manifest file does not exist.")
            path = manifest[0]
        elif kind in suffix:
            path = self.file_spec + suffix[kind]
        else: # kind=file name case
            path = os.path.join(os.path.dirname(self.file_spec), kind)

        return path

    @property
    def default_linkbase(self) -> dict:
        return {
            'doc': 'pre', # document kind for the order of financial statements
            'link_node': 'link:presentationLink',
            'arc_node': 'link:presentationArc',
            'roleRef': 'link:roleRef',
            'arc_role': 'parent-child'
        }

    @property
    def published_date(self) -> tuple[datetime, str]:
        if 'PublicDoc' in self.file_spec:
            # PublicDoc/jpcrp030000-asr-001_E00883-000_2020-12-31_01_2021-03-26
            #  split by '_'           0         1           2      3     4
            #  split by '-'   0      1   2               
            v1 = os.path.basename(self.file_spec).split('_')
            v2 = v1[0].split('-')
            date = datetime.strptime(v1[4], "%Y-%m-%d")
            period = v2[1][0]
            return date, period
        elif 'AuditDoc' in self.file_spec:
            # AuditDoc/jpaud-aar-cn-001_E00883-000_2020-12-31_01_2021-03-26
            # split by '_'       0
            raise NotImplementedError("XBRL for AuditDoc is not implemented")
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    @property
    def company_code(self) -> str:
        if 'PublicDoc' in self.file_spec:
            # PublicDoc/jpcrp030000-asr-001_E00883-000_2020-12-31_01_2021-03-26
            #  split by '_'           0         1           2      3     4
            v1 = os.path.basename(self.file_spec).split('_')
            return v1[1][0:6]
        elif 'AuditDoc' in self.file_spec:
            # AuditDoc/jpaud-aar-cn-001_E00883-000_2020-12-31_01_2021-03-26
            # split by '_'       0
            v1 = os.path.basename(self.file_spec).split('_')
            return v1[1][0:6]
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")
