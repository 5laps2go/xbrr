import os
from datetime import datetime


class BaseTaxonomy():
    """
    Taxonomy base class
    """

    def __init__(self, root: str, family: str = ""):
        self.root = root
        self.family = family
    
    def provision(self, version:str):
        raise NotImplementedError("You have to implement provision method.")
    
    def taxonomy_year(self, report_date:datetime) -> str:
        raise NotImplementedError("You have to implement taxonomy_year method.")

    def identify_version(self, namespace:str) -> str:
        raise NotImplementedError("You have to implement identify_version method.")

    def is_defined(self, uri:str):
        raise NotImplementedError("You have to implement is_defined method.")
    
    def uri_to_path(self, uri:str) -> str:
        raise NotImplementedError("You have to implement uri_to_path method.")
