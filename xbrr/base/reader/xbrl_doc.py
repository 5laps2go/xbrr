import os
from datetime import datetime, timedelta
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

    @property
    def published_date(self) -> tuple[datetime, str]:
        raise NotImplementedError("You have to implement published_date.")
    
    @property
    def report_period_end_date(self) -> datetime:
        raise NotImplementedError("You have to implement report_period_end_date.")

    @property
    def company_code(self) -> str:
        raise NotImplementedError("You have to implement company_code.")
    
    @property
    def consolidated(self) -> bool:
        raise NotImplementedError("You have to implement consolidated.")
    
    @property
    def accounting_standard(self) -> str:
        raise NotImplementedError("You have to implement accounting_standard.")
    
    @property
    def default_linkbase(self) -> dict[str, str]:
        raise NotImplementedError("You have to implement default_linkbase.")
    
    @property
    def dirname(self) -> str:
        return os.path.dirname(self.xbrl_file)
        
    @property
    def has_schema(self) -> bool:
        return self.find_path("xsd") is not None

    @property
    def xbrl(self) -> BeautifulSoup:
        return self.read_file("xbrl")

    @property
    def xsd(self) -> BeautifulSoup:
        return self.read_file("xsd")
