import os
import shutil
import pyfbi
from xbrr.edinet.client.document_client import DocumentClient
from xbrr.xbrl.reader.reader import Reader
from xbrr.edinet.reader.doc import Doc
from xbrr.edinet.reader.aspects.finance import Finance


@pyfbi.target
def check():
    _dir = os.path.join(os.path.dirname(__file__), "./data")
    if os.path.exists(_dir):
        shutil.rmtree(_dir)
    else:
        os.mkdir(_dir)
    client = DocumentClient()
    xbrl_root = client.get_xbrl("S100G2KL", save_dir=_dir, expand_level="dir")
    xbrl_doc = Doc(root_dir=xbrl_root, xbrl_kind="public")
    reader = Reader(xbrl_doc)
    print("Start Calculation")
    bs = reader.extract(Finance).bs()
    bs.to_csv("bs.csv", index=False, encoding="shift_jis")
    shutil.rmtree(_dir)


with pyfbi.watch():
    check()

pyfbi.dump("result")
pyfbi.show()
