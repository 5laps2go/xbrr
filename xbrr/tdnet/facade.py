from xbrr.tdnet.client.document_list_client import DocumentListClient
from xbrr.tdnet.client.document_client import DocumentClient
from xbrr.tdnet.reader.aspects.finance import Finance
from xbrr.tdnet.reader.aspects.forecast import Forecast
from xbrr.edinet.reader.aspects.metadata import Metadata


class APIFacade():

    @property
    def documents(self):
        client = DocumentListClient()
        return client

    @property
    def document(self):
        client = DocumentClient()
        return client


class AspectFacade():

    @property
    def Finance(self):
        return Finance

    @property
    def Forecast(self):
        return Forecast

    @property
    def Metadata(self):
        return Metadata
