from xbrr.base.reader.base_element_schema import BaseElementSchema
import bs4

class RoleSchema(BaseElementSchema):

    def __init__(self,
                 name="", label=""):
        super().__init__()
        self.name = name
        self.label = label

    @classmethod
    def create_from_reference(cls, reader, reference):
        if reader.xbrl_doc.has_schema:
            instance = reader.read_role_by_link(reference)
            instance.reference = reference
            return instance

        name = reference.split("#")[-1]
        label = ""
        instance = cls(name=name, label=label)
        return instance

    @classmethod
    def read_schema(cls, reader, xsduri, role_dic):
        xml = reader.read_by_xsduri(xsduri, 'xsd')
        for element in xml.find_all("link:roleType"):
            # <link:roleType roleURI="http://disclosure.edinet-fsa.go.jp/role/jppfs/rol_BalanceSheet" id="rol_BalanceSheet">
            #     <link:definition>貸借対照表</link:definition>
            #     <link:usedOn>link:presentationLink</link:usedOn>
            #     <link:usedOn>link:calculationLink</link:usedOn>
            #     <link:usedOn>link:definitionLink</link:usedOn>
            #     <link:usedOn>link:footnoteLink</link:usedOn>
            # </link:roleType>            
            instance = cls(name=element["id"], label=element.find("link:definition").text)
            role_dic[element["id"]] = instance

    def to_dict(self):
        return {
            "name": self.name,
            "label": self.label,
        }
