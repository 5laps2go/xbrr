from xbrr.base.reader.base_element_schema import BaseElementSchema
from typing import Callable

class RoleSchema(BaseElementSchema):

    def __init__(self, uri: str, href: str, lazy_label: Callable[[str],str]):
        super().__init__()
        self.uri = uri
        self.href = href
        self.lazy_label=lazy_label
        self._label: str = ''
    
    @property
    def label(self):
        if self._label == '':
            xsduri = self.href.split('#')[0]
            self.lazy_label(xsduri)
        return self._label

    @classmethod
    def read_role_ref(cls, reader, xml, link_node, roleRef, base_xsduri = None) -> dict[str,'RoleSchema']:
        link_node_roles = [x["xlink:role"].rsplit("/")[-1] for x in xml.find_all(link_node)]
        role_dic = {}
        for element in xml.find_all(roleRef):
            role_ref = element["xlink:href"].split("#")[-1]
            role_name = element["roleURI"].rsplit("/")[-1]

            link = element["xlink:href"]
            if not link.startswith('http') and base_xsduri != None:
                link = base_xsduri.rsplit("/",1)[0] + "/" + link
            if role_name in link_node_roles:
                role_dic[role_name] = RoleSchema(uri=element["roleURI"],
                                            href=link,
                                            lazy_label=lambda xsduri: RoleSchema.read_schema(reader, xsduri))
        return role_dic

    @classmethod
    def read_schema(cls, reader, xsduri) -> str:
        xml = reader.read_uri(xsduri)
        for element in xml.find_all("link:roleType"):
            # accounting standard='jp':     EDINET/taxonomy/2020-11-01/taxonomy/jppfs/2020-11-01/jppfs_rt_2020-11-01.xsd
            # accounting standard='ifrs':   EDINET/taxonomy/2020-11-01/taxonomy/jpigp/2020-11-01/jpigp_rt_2020-11-01.xsd
            # <link:roleType roleURI="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet" id="rol_BalanceSheet">
            #     <link:definition>貸借対照表</link:definition>
            # </link:roleType>
            if element["id"] not in reader._role_dic:
                continue
            reader._role_dic[element["id"]]._label = element.find("link:definition").text
        raise ValueError(f'schema:{xsduri} does not found')

    def to_dict(self):
        return {
            "name": self.href.split('#')[-1],
            "label": self.label,
        }
