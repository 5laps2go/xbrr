from __future__ import annotations
from typing import TYPE_CHECKING, Callable

import importlib
from bs4 import BeautifulSoup, Tag
import pandas as pd

from xbrr.base.reader.xbrl_doc import XbrlDoc

if TYPE_CHECKING:
    from xbrr.xbrl.reader.element_value import ElementValue
    from xbrr.xbrl.reader.element_schema import ElementSchema
    from xbrr.xbrl.reader.role_schema import RoleSchema

class BaseReader():
    """
    Document to Element
    """

    def __init__(self, package:str, xbrl_doc:XbrlDoc):
        self.package = package
        self.xbrl_doc = xbrl_doc

    # def link_to_path(self, link):
    #     raise NotImplementedError("You have to implement link_to_path method.")

    @property
    def custom_roles(self):
        raise NotImplementedError("You have to implement custom_roles method.")

    def presentation_version(self) -> str:
        raise NotImplementedError("You have to implement presentation_version method.")

    def find_value_names(self, candidates:list[str]) -> list[str]:
        raise NotImplementedError("You have to implement find_value_names method.")

    def find_value_name(self, findop:Callable[[str], bool]) -> str:
        raise NotImplementedError("You have to implement find_value_name method.")
    
    def findv(self, name:str) -> ElementValue | None:
        raise NotImplementedError("You have to implement findv method.")

    def get_label_uri(self, xsduri:str) -> str:
        raise NotImplementedError("You have to implement get_label_uri.")

    def get_schema_by_link(self, link:str) -> ElementSchema:
        raise NotImplementedError("You have to implement get_schema_by_link.")

    def get_role(self, role_name) -> RoleSchema:
        raise NotImplementedError("You have to implement get_role method.")
    
    def shrink_depth(self, shrink: pd.Series, base: pd.Series) -> pd.Series:
        raise NotImplementedError("You have to implement shrink_depth method.")

    # @property
    # def namespaces(self) -> dict[str, str]:
    #     raise NotImplementedError("You have to implement namespaces method.")

    def read_uri(self, uri:str) -> BeautifulSoup:
        "read xsd or xml specifed by uri"
        raise NotImplementedError("You have to implement read_uri method.")

    def read_value_by_role(self, role_link:str, preserve_cal:dict = {}, fix_cal_node:list = [], scope:str = ""):
        raise NotImplementedError("You have to implement read_value_by_role method.")

    def extract(self, aspect_cls_or_str, property=""):
        if not isinstance(aspect_cls_or_str, str):
            aspect_cls = aspect_cls_or_str
            return aspect_cls(self)

        aspect_str = aspect_cls_or_str
        imports = (
            "xbrr",
            self.package,
            "reader",
            "aspects",
            aspect_str
        )

        _class = None
        try:
            module = importlib.import_module(".".join(imports))

            def to_camel(snake_str):
                components = snake_str.split("_")
                return "".join(x.title() for x in components)

            _class_name = to_camel(aspect_str)
            _class = getattr(module, _class_name)

        except Exception as ex:
            raise Exception(f"Can't load class that matches {aspect_str} \n {ex}.")

        aspect = _class(self)
        feature = getattr(aspect, property)

        return feature
