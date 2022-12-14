import os
import re
from datetime import datetime
from xbrr.xbrl.reader.element_schema import ElementSchema
from xbrr.base.reader.base_taxonomy import BaseTaxonomy
from xbrr.edinet.reader.taxonomy import Taxonomy as EdinetTaxonomy
from xbrr.tdnet.reader.taxonomy import Taxonomy as TdnetTaxonomy

class TaxonomyRepository():

    TAXONOMY_REPO_PATTERN = re.compile('.*/(\\d+-\\d+-\\d+)')

    def __init__(self, save_dir: str = ""):
        self.taxonomies_root = os.path.join(save_dir, "external")

        # taxonomy_repo: xsd_dic for taxonomy_year
        self.taxonomy_repo:dict[str, dict[str, ElementSchema]] = {}
        # download_state: download state for taxonomy_family_version
        self.download_state:dict[str, bool] = {}

        self.taxonomies:list[BaseTaxonomy] = [
            EdinetTaxonomy(self.taxonomies_root), TdnetTaxonomy(self.taxonomies_root),
        ]

    def get_family_versions(self, report_date:datetime) -> list[str]:
        return [t.taxonomy_family_version(report_date) for t in self.taxonomies]

    def get_schema_dict(self, family_versions:list[str]) -> dict[str, ElementSchema]:
        for family_version in family_versions:
            if family_version not in self.download_state:
                self.download_state[family_version] = False

        taxonomy_year = max([x.split(':')[1] for x in family_versions])
        if taxonomy_year not in self.taxonomy_repo:
            self.taxonomy_repo[taxonomy_year] = {}

        return self.taxonomy_repo[taxonomy_year]

    def provision(self, uri, family_versions:list[str]):
        for idx, family in enumerate(family_versions):
            if self.taxonomies[idx].is_defined(uri) and not self.download_state[family]:
                self.taxonomies[idx].provision(family)
                self.download_state[family] = True

    def uri_to_path(self, uri:str) -> list[str]:
        return [t.uri_to_path(uri) for t in self.taxonomies if t.is_defined(uri)]
                