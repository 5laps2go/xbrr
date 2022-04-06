from pathlib import Path
from zipfile import ZipFile
from datetime import datetime
import requests
from xbrr.base.reader.base_taxonomy import BaseTaxonomy

class Taxonomy(BaseTaxonomy):
    TAXONOMIES = {
        "2013": "https://www.fsa.go.jp/search/20130821/editaxonomy2013New.zip",
        "2014": "https://www.fsa.go.jp/search/20140310/1c.zip",
        "2015": "https://www.fsa.go.jp/search/20150310/1c.zip",
        "2016": "https://www.fsa.go.jp/search/20160314/1c.zip",
        "2017": "https://www.fsa.go.jp/search/20170228/1c.zip",
        "2018": "https://www.fsa.go.jp/search/20180228/1c_Taxonomy.zip",
        "2019": "https://www.fsa.go.jp/search/20190228/1c_Taxonomy.zip",
        "2019_cg_ifrs": "https://www.fsa.go.jp/search/20180316/1c_Taxonomy.zip",
        "2020": "https://www.fsa.go.jp/search/20191101/1c_Taxonomy.zip",
        "2021": "https://www.fsa.go.jp/search/20201110/1c_Taxonomy.zip",
        "2022": "https://www.fsa.go.jp/search/20211109/1c_Taxonomy.zip"
    }

    def __init__(self, taxonomy_root):
        super().__init__(
            root=taxonomy_root,
            prefix="http://disclosure.edinet-fsa.go.jp/taxonomy/")

    def __reduce_ex__(self, proto):
        return type(self), (self.root,)

    def download(self, published_date:datetime, kind:str):
        year = str(self.taxonomy_year(published_date, kind))
        expand_dir = self.root.joinpath("taxonomy").joinpath("edinet")
        marker_dir = self.root.joinpath("taxonomy").joinpath(year)
        self.path = expand_dir
        taxonomy_file = self.root.joinpath(f"{year}_taxonomy.zip")

        download = False

        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            download = True

        if not marker_dir.exists():
            marker_dir.mkdir(parents=True, exist_ok=True)
            download = True

        if download:
            # Download
            r = requests.get(self.TAXONOMIES[year], stream=True)
            with taxonomy_file.open(mode="wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            # Extract
            with ZipFile(taxonomy_file, "r") as zip:
                for f in zip.namelist():
                    if not zip.getinfo(f).is_dir():
                        dirs = Path(f).parts
                        # Avoid Japanese path
                        taxonomy_at = dirs.index("taxonomy") if "taxonomy" in dirs else -1
                        if taxonomy_at > 0 and len(dirs) > (taxonomy_at + 1):
                            dirs = dirs[(dirs.index("taxonomy") + 1):]
                            _to = expand_dir.joinpath("/".join(dirs))
                            _to.parent.mkdir(parents=True, exist_ok=True)
                            with _to.open("wb") as _to_f:
                                _to_f.write(zip.read(f))

            taxonomy_file.unlink()

        return expand_dir

    def taxonomy_year(self, published_date:datetime, kind:str) -> str:
        taxonomy_year = ""
        for y in sorted(list(self.TAXONOMIES.keys()), reverse=True):
            boarder_date = datetime(int(y[:4]), 3, 31)
            if kind[0] in ("q", "h") and published_date > boarder_date:
                taxonomy_year = y
            elif published_date >= boarder_date:
                if y == 2019:
                    taxonomy_year = "2019_cg_ifrs"
                else:
                    taxonomy_year = y

            if taxonomy_year:
                break
        return taxonomy_year
