from xbrr.base.reader.base_element_schema import BaseElementSchema
import bs4

class RoleSchema(BaseElementSchema):

    def __init__(self,
                 uri="", href="", lazy_label=None):
        super().__init__()
        self.uri = uri
        self.href = href
        self.lazy_label=lazy_label
        self._label = None
    
    @property
    def label(self):
        if self._label is None:
            xsduri = self.href.split('#')[-1]
            self.lazy_label(xsduri)
        return self._label

    @classmethod
    def create_role_schema(cls, reader, roleref_element):
        link = roleref_element["xlink:href"]
        role_name = link.split("#")[-1]
        return RoleSchema(uri=roleref_element["roleURI"],
                          href=link,
                          lazy_label=lambda xsduri: RoleSchema.read_schema(reader, xsduri))

    @classmethod
    def read_schema(cls, reader, xsduri):
        xml = reader.read_by_xsduri(xsduri, 'xsd')
        for element in xml.find_all("link:roleType"):
            # accounting standard='jp':     EDINET/taxonomy/2020-11-01/taxonomy/jppfs/2020-11-01/jppfs_rt_2020-11-01.xsd
            # accounting standard='ifrs':   EDINET/taxonomy/2020-11-01/taxonomy/jpigp/2020-11-01/jpigp_rt_2020-11-01.xsd
            # <link:roleType roleURI="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet" id="rol_BalanceSheet">
            #     <link:definition>貸借対照表</link:definition>
            # </link:roleType>
            reader._role_dic[element["id"]]._label = element.find("link:definition").text

    def to_dict(self):
        return {
            "name": self.href.split('#')[-1],
            "label": self.label,
        }
