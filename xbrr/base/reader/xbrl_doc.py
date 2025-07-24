import os
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from xbrr.base.reader.base_doc import BaseDoc


class XbrlDoc(BaseDoc):

    def __init__(self, package, root_dir:str|Path="", xbrl_file=""):
        super().__init__(package, root_dir=root_dir, xbrl_file=xbrl_file)
        self._cache = {}

    def read_file(self, kind:str) -> BeautifulSoup:
        path = self.find_path(kind)
        if (not os.path.isfile(path)):
            return BeautifulSoup()  # no content
        if kind not in self._cache:
            with open(path, encoding="utf-8-sig") as f:
                self._cache[kind] = BeautifulSoup(f, "lxml-xml")
        return self._cache[kind]
