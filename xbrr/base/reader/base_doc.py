import os
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from xbrr.base.reader.base_taxonomy import BaseTaxonomy


class BaseDoc():
    """
    Submitted Document base class
    """

    def __init__(self, package, root_dir:str|Path="", xbrl_file=""):
        self.package = package
        self.root_dir = str(root_dir)
        self.xbrl_file = xbrl_file
    
    def find_path(self, kind: str) -> str:
        raise NotImplementedError("You have to implement find_path method.")

    def read_file(self, kind: str) -> BeautifulSoup:
        raise NotImplementedError("You have to implement read_file method.")

    @property
    def published_date(self) -> tuple[datetime, str]:
        raise NotImplementedError("You have to implement published_date.")
    
    @property
    def fiscal_year_date(self) -> datetime:
        raise NotImplementedError("You have to implement fiscal_year_date.")

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
