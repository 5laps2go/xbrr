import xbrr.edinet as _edinet
import xbrr.tdnet as _tdnet

edinet = _edinet
tdnet = _tdnet

from xbrr.xbrl.reader.reader import Reader
class ReaderFacade():
    def read(self, xbrl_doc):
        return Reader(xbrl_doc)

reader = ReaderFacade()
