from datetime import datetime
from pathlib import Path

class BaseTaxonomy():
    """
    Taxonomy base class
    """

    def __init__(self, root: Path, prefix: str = ""):
        self.root = root
        self.prefix = prefix
        self.path: Path
    
    def download(self, published_date:datetime, kind:str):
        raise NotImplementedError("You have to implement download method.")
    
    def taxonomy_year(self, published_date:datetime, kind:str="a") -> str:
        raise NotImplementedError("You have to implement taxonomy_year method.")
