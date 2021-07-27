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


    def find_path(self, kind):
        if kind != "xbrl":
            return None

        return self.xbrl_file