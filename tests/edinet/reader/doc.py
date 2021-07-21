import os
from xbrr.base.reader.base_doc import BaseDoc
from bs4 import BeautifulSoup

class Doc(BaseDoc):
    """
    Doc for test to provide single xbrl file
    """

    def __init__(self, xbrl_file):
        super().__init__("edinet", xbrl_file=xbrl_file)
        self.file_spec = os.path.splitext(self.xbrl_file)[0]


    def _find_file(self, kind, as_xml=True):
        if kind != "xbrl":
            return None

        path = self.xbrl_file
        if as_xml:
            xml = None
            with open(path, encoding="utf-8-sig") as f:
                xml = BeautifulSoup(f, "lxml-xml")
            return xml
        else:
            return path
