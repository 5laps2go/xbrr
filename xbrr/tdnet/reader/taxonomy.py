import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests

from xbrr.base.reader.base_taxonomy import BaseTaxonomy


class Taxonomy(BaseTaxonomy):
    TAXONOMIES = {
        "2014": "https://www.jpx.co.jp/equities/listing/disclosure/xbrl/nlsgeu000005vk0b-att/61_taxonomy.zip",
    }

    def __init__(self, taxonomy_root):
        super().__init__(
            root = taxonomy_root,
            family = 'tdnet',
            prefix = "http://www.xbrl.tdnet.info/taxonomy/")

    def __reduce_ex__(self, proto):
        return type(self), (self.root,)

    def download(self, published_date:datetime, kind:str):
        year = str(self.taxonomy_year(published_date))
        self._download(year)
    
    def provision(self, family_version:str):
        year = family_version.split(':')[1]
        self._download(year)

    def _download(self, year:str):
        expand_dir = os.path.join(os.path.join(self.root, "taxonomy"), "tdnet")
        marker_dir = os.path.join(os.path.join(self.root, "taxonomy"), year)
        self.path = expand_dir
        taxonomy_file = os.path.join(self.root, f"{year}_taxonomy.zip")

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
                            _to = Path(expand_dir).joinpath("/".join(dirs))
                            _to.parent.mkdir(parents=True, exist_ok=True)
                            with _to.open("wb") as _to_f:
                                _to_f.write(zip.read(f))

            r = requests.get(self.TAXONOMIES[year], stream=True)
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

        return expand_dir

    def taxonomy_year(self, report_date:datetime) -> str:
        taxonomy_year = ""
        for y in sorted(list(self.TAXONOMIES.keys()), reverse=True):
            boarder_date = datetime(int(y[:4]), 3, 31)
            if report_date > boarder_date:
                taxonomy_year = y
                break
        return taxonomy_year
