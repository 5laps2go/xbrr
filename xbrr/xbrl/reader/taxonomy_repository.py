import os
import re
from datetime import datetime

from xbrr.base.reader.base_taxonomy import BaseTaxonomy
from xbrr.edinet.reader.taxonomy import Taxonomy as EdinetTaxonomy
from xbrr.tdnet.reader.taxonomy import Taxonomy as TdnetTaxonomy
from xbrr.xbrl.reader.element_schema import ElementSchema
from xbrr.xbrl.reader.schema_dicts import SchemaDicts


class TaxonomyRepository():

    def __init__(self, save_dir: str = ""):
        self.taxonomies_root = os.path.join(save_dir, "external")

        # taxonomy_repo: xsd_dic for taxonomy_year
        self.taxonomy_repo:dict[str, dict[str, ElementSchema]] = {}

        self.taxonomies:list[BaseTaxonomy] = [
            EdinetTaxonomy(self.taxonomies_root), TdnetTaxonomy(self.taxonomies_root),
        ]

    def get_schema_dicts(self, nsdecls:dict[str, str]) -> SchemaDicts:
        schema_dicts = SchemaDicts()
        for taxonomy in self.taxonomies:
            versions = [taxonomy.identify_version(nsdecl) for nsdecl in nsdecls.values() if taxonomy.family in nsdecl]
            if ''.join(versions):
                version = max(versions)
                taxonomy.provision(version)
                dict = self.taxonomy_repo.get(version, {})
                if not dict:
                    self.taxonomy_repo[version] = dict
                schema_dicts.add(version, dict)
        return schema_dicts

    def uri_to_path(self, uri:str) -> list[str]:
        return [t.uri_to_path(uri) for t in self.taxonomies if t.is_defined(uri)]
                