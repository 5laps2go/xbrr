import os
from datetime import datetime

class BaseTaxonomy():
    """
    Taxonomy base class
    """

    def __init__(self, root: str, family: str = "", prefix: str = ""):
        self.root = root
        self.family = family
        self.prefix = prefix
        self.path: str
    
    def download(self, published_date:datetime, kind:str):
        raise NotImplementedError("You have to implement download method.")
    
    def provision(self, family_version:str):
        raise NotImplementedError("You have to implement provision method.")
    
    def taxonomy_year(self, report_date:datetime) -> str:
        raise NotImplementedError("You have to implement taxonomy_year method.")

    def taxonomy_family_version(self, report_date:datetime) -> str:
        return f'{self.family}:' + self.taxonomy_year(report_date)

    def is_defined(self, uri:str):
        return uri.startswith(self.prefix)
    
    def uri_to_path(self, uri:str) -> str:
        return os.path.join(self.path, uri.replace(self.prefix, ""))