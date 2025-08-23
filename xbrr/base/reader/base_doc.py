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
