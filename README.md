# XBRR: eXtensible Business Report Reader

[![PyPI version](https://badge.fury.io/py/xbrr.svg)](https://badge.fury.io/py/xbrr)
[![Build Status](https://travis-ci.org/chakki-works/xbrr.svg?branch=master)](https://travis-ci.org/chakki-works/xbrr)
[![codecov](https://codecov.io/gh/chakki-works/xbrr/branch/master/graph/badge.svg)](https://codecov.io/gh/chakki-works/xbrr)

Features:

* API: Download the documents from official publication site.
* Reader: Extract contents from XBRL.

Supported documents:

* Japan
  * API: [EDINET](http://disclosure.edinet-fsa.go.jp/)
  * Reader: Mainly supports annual reports disclosed on EDINET and TDNET
* America
  * API: Comming soon
  * Reader: Comming soon

**We are welcome the contribution to support other countries API & Documents!**

## Install

```
pip install xbrr
```

## How to use

(Examples are Japanese EDINET API and annual report).

### 1. API

Download the documents from [EDINET](http://disclosure.edinet-fsa.go.jp/).

#### 1.1 Get document list of specific day

```py
import xbrr


documents = xbrr.xxx.api.documents.get("2019-01-31")     # xxx: edinet or tdnet
print(f"Number of documents is {len(documents.list)}")
print(f"Title of first document is {documents.list[0].title}")
```

#### 1.2 Get document by document id

```py
from pathlib import Path
import xbrr


xbrl_path = xbrr.xxx.api.document.get_xbrl("S100FGR9", save_dir=Path.cwd())  # xxx: edinet or tdnet
pdf_path = xbrr.xxx.api.document.get_pdf("S100FGR9", save_dir=Path.cwd())    # xxx: edinet or tdnet
```

Each XBRL includes taxonomy information. If you want to deal with these files, execute the following.

```py
xbrl_dir = xbrr.xxx.api.document.get_xbrl("S100FGR9", save_dir=Path.cwd(), expand_level="dir")
```


### 2. Reader

Extract contents from XBRL.

```py
xbrl = xbrr.reader.read("path/to/xbrl/file")
content = xbrl.extract(xbrr.xxx.aspects.Business).policy_environment_issue_etc.value # xxx: edinet or tdnet
```

Extract financial statements.

```py
xbrl_dir = xbrr.reader.read("path/to/xbrl/dir")
xbrl_dir.extract(xbrr.xxx.aspects.Finance).bs.to_csv("bs.csv", index=False) # xxx: edinet or tdnet
```

![bs.png](./docs/images/bs.png)

Please refer to the supported aspects from the following links.

* [EDINET](https://github.com/chakki-works/xbrr/blob/master/docs/edinet.md)
