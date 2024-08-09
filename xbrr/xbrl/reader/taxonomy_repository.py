import os
import re
from datetime import datetime
from functools import lru_cache

from bs4 import BeautifulSoup

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
        self.read_uri_taxonomy = lru_cache(maxsize=50)(self.__read_uri_taxonomy)

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
    
    def find_xsduri(self, namespace:str) -> str:
        for taxonomy in self.taxonomies:
            if taxonomy.is_defined(namespace):
                return taxonomy.implicit_xsd(namespace)
        raise NameError(f'unknown namespace found:{namespace}')


    def read_uri(self, uri:str) -> BeautifulSoup:
        "read xsd or xml specifed by uri"
        # assert os.path.isfile(uri) or uri.startswith('http:'), 'no xsduri found: {}'.format(uri)
        if not uri.startswith('http'):
            return self.read_file(uri)
        return self.read_uri_taxonomy(uri)
    
    def __read_uri_taxonomy(self, uri) -> BeautifulSoup:
        path = ''
        paths = self.uri_to_path(uri)
        if len(paths) > 0:
            path = paths[0]
        elif not uri.startswith('http://www.xbrl.org/'):
            raise Exception("_uri_to_path", uri)
        return self.read_file(path)
    
    def read_file(self, path:str) -> BeautifulSoup:
        if (not os.path.isfile(path)):
            return BeautifulSoup()  # no content
        with open(path, encoding="utf-8-sig") as f:
            xml = BeautifulSoup(f, "lxml-xml")
        return xml
