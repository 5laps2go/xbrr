import errno
import glob
import os
import subprocess
from datetime import datetime
from subprocess import PIPE

from bs4 import BeautifulSoup

from xbrr.base.reader.base_taxonomy import BaseTaxonomy
from xbrr.base.reader.xbrl_doc import XbrlDoc
from xbrr.edinet.reader.taxonomy import Taxonomy as EdinetTaxonomy
from xbrr.tdnet.reader.taxonomy import Taxonomy as TdnetTaxonomy


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
        # around 2014, -calculation.xml,-presentation.xml after 2020 -cal.xml,-pre.xml
        suffix = {
            "xbrl": ".xbrl", "xsd": ".xsd", "cal": "-cal*.xml", "def": "-def.xml",
            "lab": "-lab.xml", "lab-en": "-lab-en.xml", "pre": "-pre*.xml",
            }

        if kind == "man":
            path = os.path.join(os.path.dirname(self.file_spec), "manifest.xml")
            if len(path)==0:
                raise Exception(f"manifest file does not exist.")
        elif kind in suffix:
            path = self.file_spec + suffix[kind]
            files = glob.glob(path)
            if len(files)>0: return files[0]
        else: # kind=file name case
            path = os.path.join(os.path.dirname(self.file_spec), kind)

        return path

    @property
    def default_linkbase(self) -> dict:
        if 'Attachment' in self.file_spec:
            return {
                'doc': 'pre', # document kind for the order of financial statements
                'link_node': 'link:presentationLink',
                'arc_node': 'link:presentationArc',
                'roleRef': 'link:roleRef',
                'arc_role': 'parent-child'
            }

        assert 'Summary' in self.file_spec or '/./'  in self.file_spec
        return {
            'doc': 'def', # document kind for the order of financial statements
            'link_node': 'definitionLink',
            'arc_node': 'definitionArc',
            'roleRef': 'roleRef',
            'arc_role': 'domain-member'
        }

    @property
    def published_date(self) -> tuple[datetime, str]:
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

    @property
    def company_code(self) -> str:
        if 'Attachment' in self.file_spec:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            return v[2]
        elif 'Summary' in self.file_spec or '/./' in self.file_spec:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            return v[2]
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    def _prepare_xbrl(self, xsd_file: str) -> str:
        """process ixbrl to xbrl
        """
        if not os.path.isfile(xsd_file):
            raise Exception(f"XSD file does not exist.")
        xsl_file = "/usr/local/share/inlinexbrl/processor/Main_exslt.xsl"

        self.file_spec = os.path.splitext(xsd_file)[0]
        manifest_file = self.find_path('man')
        if os.path.isfile(manifest_file):
            infile = manifest_file
            with open(manifest_file, encoding="utf-8-sig") as f:
                manifest_xml = BeautifulSoup(f, "lxml-xml")
            xbrl_file = os.path.join(os.path.dirname(self.file_spec),  # type: ignore
                                    manifest_xml.find('instance')['preferredFilename'])  # type: ignore
        else:
            infile = self.file_spec+"-ixbrl.htm"
            xbrl_file = self.file_spec + ".xbrl"

        if os.path.isfile(xbrl_file): return xbrl_file
        command = "xalan -q -out %s -xsl %s -in %s" % (xbrl_file, xsl_file, infile)
        proc = subprocess.run(command, shell=True, stdout=PIPE, stderr=PIPE, text=True)

        if not os.path.isfile(xbrl_file):
            raise Exception(f"XBRL file is not generated.")
        return xbrl_file