import os
from xbrr.base.reader.base_doc import BaseDoc
from bs4 import BeautifulSoup
import re

class Doc(BaseDoc):
    """
    Doc for test to provide single xbrl file
    """

    def __init__(self, xbrl_file):
        super().__init__("edinet", xbrl_file=xbrl_file)
        self.file_spec = os.path.splitext(self.xbrl_file)[0]

    @property
    def taxonomy_year(self):
        return re.findall(r'20[0-9]{2}', self.file_spec)[-1] # the last 20xx is taxonomy year

    def find_path(self, kind):
        if kind != "xbrl":
            return None
        return self.xbrl_file
    
    def read_file(self, kind):
        if kind != "xbrl":
            return None
        with open(self.xbrl_file, encoding="utf-8-sig") as f:
            xml = BeautifulSoup(f, "lxml-xml")
        return xml

    def find_xsduri(self, namespace):
        return "unknown.xsd"

    def create_taxonomies(self, root_dir):
        return None

