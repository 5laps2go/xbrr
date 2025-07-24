from datetime import datetime


class Document():

    def __init__(self,
                 document_id="S1000001",
                 sec_code="10000",
                 has_xbrl=False,
                 has_pdf=False,
                 submitted_date="1000-01-01 12:01",
                 title="",
                 pdf_document_id = ""
                 ):
        self.document_id = document_id
        self.sec_code = sec_code
        self.submitted_date = submitted_date
        self.title = title
        self.has_xbrl = has_xbrl
        self.has_pdf = has_pdf
        self.pdf_document_id = pdf_document_id

    @classmethod
    def create(cls, body: dict) -> "Document":
        def to_date(value, format):
            f = "%Y-%m-%d" if format == "ymd" else "%Y-%m-%d %H:%M:%S"
            return datetime.strptime(value, f).strftime(f)

        def to_bool(value):
            return True if value is not None else False
        
        def to_docid(value):
            if value is None: return ''
            return value.split('/')[-1].split('.')[0]

        tdnet = body['Tdnet']
        instance = cls(
            document_id=to_docid(tdnet["url_xbrl"]),
            sec_code=tdnet["company_code"],
            submitted_date=to_date(tdnet["pubdate"], "ymd_hms"),
            title=tdnet["title"],
            has_xbrl=to_bool(tdnet["url_xbrl"]),
            has_pdf=to_bool(tdnet["document_url"]),
            pdf_document_id=to_docid(tdnet["document_url"])
        )

        return instance

    @property
    def is_outdated(self):
        return False

    @property
    def is_withdrew(self):
        return False

    def get_pdf(self, save_dir: str = "", file_name: str = ""):
        from xbrr.tdnet.client.document_client import DocumentClient
        client = DocumentClient()
        return client.get_pdf(self.pdf_document_id, save_dir, file_name)

    def get_xbrl(self, save_dir: str = "", file_name: str = ""):
        from xbrr.tdnet.client.document_client import DocumentClient
        client = DocumentClient()
        return client.get_xbrl(self.document_id, save_dir, file_name)
