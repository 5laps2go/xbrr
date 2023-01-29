import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests

from xbrr.base.reader.base_taxonomy import BaseTaxonomy


class Taxonomy(BaseTaxonomy):
    TAXONOMIES = {
        "2011-06-30": "http://www.xbrl.tdnet.info/download/taxonomy/tse-ed-2011-06-30.zip",
        "2014-01-12": "https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/61_taxonomy.zip",
    }

    def __init__(self, taxonomy_root):
        super().__init__(
            root = taxonomy_root,
            family = 'tdnet')
        self.prefix = "http://www.xbrl.tdnet.info/taxonomy/"
        self.expand_dir = os.path.join(os.path.join(self.root, "taxonomy"), "tdnet")

    def __reduce_ex__(self, proto):
        return type(self), (self.root,)

    def identify_version(self, namespace:str) -> str:
        version = ''
        m = re.match(r'http://.*.tdnet.info/taxonomy/jp/tse/tdnet/[^/]{2}/[^/]/(\d{4}-\d{2}-\d{2})', namespace)
        if m != None:
            version = m.group(1)
        return version

    def provision(self, version:str):
        self.__download(version, self.TAXONOMIES)

    def is_defined(self, uri:str):
        return uri.startswith(self.prefix)
    
    def uri_to_path(self, uri:str) -> str:
        return os.path.join(self.expand_dir, uri.replace(self.prefix, ""))

    def __download(self, key:str, taxonomies:dict[str,str]):
        marker_dir = os.path.join(os.path.join(self.root, "taxonomy"), key)
        taxonomy_file = os.path.join(self.root, f"{key}_taxonomy.zip")

        download = False

        if not os.path.isdir(self.root):
            os.makedirs(self.root, exist_ok=True)
            download = True

        if not os.path.isdir(marker_dir):
            os.makedirs(marker_dir, exist_ok=True)
            download = True

        if download:
            # Download
            def extract_taxonomy(f, zip):
                    if not zip.getinfo(f).is_dir():
                        dirs = Path(f).parts
                        taxonomy_at = dirs.index("taxonomy") if "taxonomy" in dirs else -1
                        if taxonomy_at > 0 and len(dirs) > (taxonomy_at + 1):
                            dirs = dirs[(dirs.index("taxonomy") + 1):]
                            _to = Path(self.expand_dir).joinpath("/".join(dirs))
                            _to.parent.mkdir(parents=True, exist_ok=True)
                            with _to.open("wb") as _to_f:
                                _to_f.write(zip.read(f))

            r = requests.get(taxonomies[key], stream=True)
            with open(taxonomy_file, mode="wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            # Extract zip files
            with ZipFile(taxonomy_file, "r") as zip:
                # zip.extractall(self.root)
                for name in zip.namelist():
                    if name.endswith('.zip'):
                        # We have a zip within a zip
                        zfiledata = BytesIO(zip.read(name))
                        with ZipFile(zfiledata) as zip2:
                            for f in zip2.namelist():
                                extract_taxonomy(f, zip2)
                    else:
                        extract_taxonomy(name, zip)
            os.remove(taxonomy_file) # .unlink()

        return self.expand_dir
