import os
import re
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

import requests

from xbrr.base.reader.base_taxonomy import BaseTaxonomy


class Taxonomy(BaseTaxonomy):
    TAXONOMIES = {
        "2008-02-01": "https://www.fsa.go.jp/singi/edinet/20080208/01.zip",
        "2009-03-09": "https://www.fsa.go.jp/search/20090309/editaxonomy20090309.zip",
        "2010-03-11": "https://www.fsa.go.jp/search/20100311/editaxonomy20100311.zip",
        "2011-03-14": "https://www.fsa.go.jp/search/20110314/editaxonomy20110314.zip",
        "2012-01-25": "https://www.fsa.go.jp/search/20120314/editaxonomy20120125.zip",
        "2013-03-01": "https://www.fsa.go.jp/search/20130301/editaxonomy2013.zip",
        # the above has not taxonomy folder and its prefix begins with "http://info.edinet-fsa.go.jp/"
        # the below has taxonomy folder, after 20140401
        "2013-08-31": "https://www.fsa.go.jp/search/20140310/1c.zip",
        "2015-03-31": "https://www.fsa.go.jp/search/20150310/1c.zip",
        "2016-02-29": "https://www.fsa.go.jp/search/20160314/1c.zip",
        "2017-02-28": "https://www.fsa.go.jp/search/20170228/1c.zip",
        "2018-02-28": "https://www.fsa.go.jp/search/20180228/1c_Taxonomy.zip",
        "2018-03-31": "https://www.fsa.go.jp/search/20180316/1c_Taxonomy.zip",
        "2019-02-28": "https://www.fsa.go.jp/search/20190228/1c_Taxonomy.zip",
        "2019-11-01": "https://www.fsa.go.jp/search/20191101/1c_Taxonomy.zip",
        "2020-11-01": "https://www.fsa.go.jp/search/20201110/1c_Taxonomy.zip",
        "2021-11-01": "https://www.fsa.go.jp/search/20211109/1c_Taxonomy.zip",
        "2022-11-01": "https://www.fsa.go.jp/search/20221108/1c_Taxonomy.zip",
    }

    def __init__(self, taxonomy_root: str):
        super().__init__(
            root=taxonomy_root,
            family='edinet')
        self.prefix=("http://disclosure.edinet-fsa.go.jp/taxonomy/","http://info.edinet-fsa.go.jp/")
        self.expand_dir = os.path.join(os.path.join(self.root, "taxonomy"), "edinet")

    def __reduce_ex__(self, proto):
        return type(self), (self.root,)

    def identify_version(self, namespace:str) -> str:
        # old style:     http://info.edinet-fsa.go.jp/jp/fr/gaap/o/rt/2013-03-01
        # current style: http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2019-11-01/jppfs_cor
        version = ''
        m = re.match(r'http://.*.edinet-fsa.go.jp/(taxonomy/[a-z_/]+/(\d{4}-\d{2}-\d{2})/[a-z_]+$|jp/[a-z_/]+/(\d{4}-\d{2}-\d{2})$)', namespace)
        if m != None:
            version = m.group(2) if m.group(2) else m.group(3)
        return version

    def provision(self, version:str):
        self.__download(version, self.TAXONOMIES)

    def is_defined(self, uri:str):
        return uri.startswith(self.prefix)
    
    def implicit_xsd(self, namespace:str) -> str:
        # http://info.edinet-fsa.go.jp/jp/fr/gaap/t/cte/2012-01-25 -> ~/jp/fr/gaap/t/cte/2012-01-25/t-cte.xsd
        oldhttp = 'http://info.edinet-fsa.go.jp/'
        basename = namespace.replace(oldhttp,'')
        split = basename.split('/')
        xsd_file = '-'.join([split[0]+split[1],split[3],split[4],split[5]]) + '.xsd'
        return namespace + '/' + xsd_file

    def uri_to_path(self, uri:str) -> str:
        if isinstance(self.prefix, tuple):
            for pre in self.prefix:
                if uri.startswith(pre):
                    return os.path.join(self.expand_dir, uri.replace(pre, ""))
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
            r = requests.get(taxonomies[key], stream=True)
            with open(taxonomy_file, mode="wb") as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)

            # Extract
            with ZipFile(taxonomy_file, "r") as zip:
                for f in zip.namelist():
                    if not zip.getinfo(f).is_dir():
                        dirs = Path(f).parts
                        if key <= '2013-03-01':
                            jp_at = dirs.index("jp") if "jp" in dirs else -1
                            if len(dirs) > jp_at:
                                dirs = dirs[(dirs.index("jp")):]
                                _to = Path(self.expand_dir).joinpath("/".join(dirs))
                                _to.parent.mkdir(parents=True, exist_ok=True)
                                with _to.open("wb") as _to_f:
                                    _to_f.write(zip.read(f))
                        # Avoid Japanese path
                        taxonomy_at = dirs.index("taxonomy") if "taxonomy" in dirs else -1
                        if taxonomy_at > 0 and len(dirs) > (taxonomy_at + 1):
                            dirs = dirs[(dirs.index("taxonomy") + 1):]
                            _to = Path(self.expand_dir).joinpath("/".join(dirs))
                            _to.parent.mkdir(parents=True, exist_ok=True)
                            with _to.open("wb") as _to_f:
                                _to_f.write(zip.read(f))

            os.remove(taxonomy_file) # .unlink()
        return self.expand_dir

