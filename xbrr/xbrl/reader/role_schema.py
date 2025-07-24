from typing import Callable, cast

from bs4 import BeautifulSoup, Tag
from xbrr.base.reader.base_element_schema import BaseElementSchema

class RoleSchema(BaseElementSchema):

    def __init__(self, uri: str, href: str, lazy_label: Callable[[str],None]):
        super().__init__()
        self.uri = uri
        self.href = href
        self.lazy_label=lazy_label
        self._label: str = ''
    
    @property
    def label(self) -> str:
        if self._label == '':
            xsduri = self.href.split('#')[0]
            self.lazy_label(xsduri)
        return self._label

    @classmethod
    def read_role_ref(cls, xml:BeautifulSoup, link_node, roleRef, lazy_uri_reader:Callable[[str],BeautifulSoup], base_xsduri = None) -> dict[str,'RoleSchema']:
        link_node_roles = [cast(str,cast(Tag,x)["xlink:role"]).rsplit("/")[-1] for x in xml.find_all(link_node)]
        role_dic = {}
        for element in xml.find_all(roleRef):
            assert isinstance(element, Tag)
            role_ref = cast(str,element["xlink:href"]).split("#")[-1]
            role_name = cast(str,element["roleURI"]).rsplit("/")[-1]

            link = cast(str,element["xlink:href"])
            if not link.startswith('http') and base_xsduri != None:
                link = base_xsduri.rsplit("/",1)[0] + "/" + link
            if role_name in link_node_roles:
                role_dic[role_name] = RoleSchema(uri=cast(str,element["roleURI"]),
                                            href=link,
                                            lazy_label=lambda xsduri: RoleSchema.read_schema(xsduri, role_dic, lazy_uri_reader))
        return role_dic

    @classmethod
    def read_schema(cls, xsduri:str, role_dic:dict[str,'RoleSchema'], lazy_uri_reader:Callable[[str],BeautifulSoup]):
        xml = lazy_uri_reader(xsduri)
        for element in xml.find_all("link:roleType"):
            # accounting standard='jp':     EDINET/taxonomy/2020-11-01/taxonomy/jppfs/2020-11-01/jppfs_rt_2020-11-01.xsd
            # accounting standard='ifrs':   EDINET/taxonomy/2020-11-01/taxonomy/jpigp/2020-11-01/jpigp_rt_2020-11-01.xsd
            # <link:roleType roleURI="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet" id="rol_BalanceSheet">
            #     <link:definition>貸借対照表</link:definition>
            # </link:roleType>
            assert isinstance(element, Tag)
            if element["id"] not in role_dic:
                continue
            role_dic[cast(str,element["id"])]._label = cast(Tag,element.find("link:definition")).text
        raise ValueError(f'schema:{xsduri} does not found')

    def to_dict(self) -> dict[str,str]:
        return {
            "name": self.href.split('#')[-1],
            "label": self.label,
        }
