import os
import errno
import glob
from datetime import datetime
from xbrr.base.reader.xbrl_doc import XbrlDoc
from xbrr.edinet.reader.taxonomy import Taxonomy as EdinetTaxonomy
from xbrr.tdnet.reader.taxonomy import Taxonomy as TdnetTaxonomy
import subprocess
from subprocess import PIPE
from typing import Tuple, Dict

class Doc(XbrlDoc):

    def __init__(self, root_dir="", xbrl_kind=""):

        def _glob_list(folders):
            for folder in folders:
                xsd_files = glob.glob(os.path.join(root_dir, folder+"/*.xsd"))
                if xsd_files: return xsd_files
            return []
        def _xbrl_file(root_dir, kind):
            folder_dict = {'public': ['XBRLData/Attachment'], 'summary': ['XBRLData/Summary','.']}
            xsd_files = _glob_list(folder_dict[kind])
            if not xsd_files:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), folder_dict[kind])
            xbrl_file = self._prepare_xbrl(xsd_files[0])
            return xbrl_file
        
        xbrl_file=_xbrl_file(root_dir, xbrl_kind)
        self.file_spec = os.path.splitext(xbrl_file)[0]
        super().__init__("tdnet", root_dir=root_dir, xbrl_file=xbrl_file)

    def find_path(self, kind) -> str:
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

    @property
    def default_linkbase(self) -> dict:
        if 'Attachment' in self.file_spec:
            return {
                'doc': self.pre,
                'link_node': 'link:presentationLink',
                'arc_node': 'link:presentationArc',
                'roleRef': 'link:roleRef',
                'arc_role': 'parent-child'
            }

        assert 'Summary' in self.file_spec or '/./'  in self.file_spec
        return {
            'doc': self.def_,
            'link_node': 'definitionLink',
            'arc_node': 'definitionArc',
            'roleRef': 'roleRef',
            'arc_role': 'domain-member'
        }

    @property
    def published_date(self) -> Tuple[datetime, str]:
        if 'Attachment' in self.file_spec:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            date = datetime.strptime("%s-%s-%s" % (v[7], v[8], v[9]), "%Y-%m-%d")
            period = v[1][0]
            return date, period
        elif 'Summary' in self.file_spec or '/./' in self.file_spec:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            date = datetime.strptime("%s-%s-%s" % (v[3][:4], v[3][4:6], v[3][6:8]), "%Y-%m-%d")
            period = v[1][0]
            return date, period
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    def create_taxonomies(self, root_dir) -> Dict[str, object]:
        if 'Attachment' in self.file_spec:
            etxnmy = EdinetTaxonomy(root_dir)
            ttxnmy = TdnetTaxonomy(root_dir)
            return {etxnmy.prefix: etxnmy, ttxnmy.prefix: ttxnmy}

        assert 'Summary' in self.file_spec or '/./'  in self.file_spec
        ttxnmy = TdnetTaxonomy(root_dir)
        return {ttxnmy.prefix: ttxnmy}

    def _prepare_xbrl(self, xsd_file: str) -> str:
        """process ixbrl to xbrl
        """
        if not os.path.isfile(xsd_file):
            raise Exception(f"XSD file does not exist.")
        xsl_file = "/usr/local/share/inlinexbrl/processor/Main_exslt.xsl"

        self.file_spec = os.path.splitext(xsd_file)[0]
        ixbrl_file = self.file_spec+"-ixbrl.htm"
        manifest_file = self.find_path('man')
        infile = manifest_file if os.path.isfile(manifest_file) else ixbrl_file
        xbrl_file = self.file_spec + ".xbrl"

        command = "xsltproc -o %s %s %s" % (xbrl_file, xsl_file, infile)
        proc = subprocess.run(command, shell=True, stdout=PIPE, stderr=PIPE, text=True)

        if not os.path.isfile(xbrl_file):
            raise Exception(f"XBRL file is not generated.")
        return xbrl_file