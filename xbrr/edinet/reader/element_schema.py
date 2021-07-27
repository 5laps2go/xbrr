from xbrr.base.reader.base_element_schema import BaseElementSchema
import bs4

class ElementSchema(BaseElementSchema):

    def __init__(self,
                 name="", reference="", label="", alias="",
                 abstract="", data_type="",
                 period_type="", balance=""):
        super().__init__()
        self.name = name
        self.reference = reference # TODO: omit it because name has ns prefix_element name
        self.label = label
        self.alias = alias
        self.abstract = abstract
        self.data_type = data_type
        self.period_type = period_type
        self.balance = balance
        self.verbose_label = ""

    def set_alias(self, alias):
        self.alias = alias
        return self

    @classmethod
    def create_from_reference(cls, reader, reference):
        if not reader.xbrl_doc.has_schema: # for test purpose only
            name = reference.split("#")[-1]
            instance = cls(name=name, reference=reference)
            return instance

        instance = reader.read_by_link(reference)
        instance.reference = reference
        return instance


    @classmethod
    def read_schema(cls, reader, xsduri):
        xsd_dic = {}
        xml = reader.read_by_xsduri(xsduri, 'xsd')
        for element in xml.find_all("xsd:element"):
            # <xsd:element id="jpcrp030000-asr_E00436-000_Subsidy" xbrli:balance="credit" xbrli:periodType="duration" abstract="false" name="Subsidy" nillable="true" substitutionGroup="xbrli:item" type="xbrli:monetaryItemType" />
            instance = cls(name=element["id"], alias=element["name"], 
                            data_type=element["type"], 
                            period_type=element["xbrli:periodType"],
                            abstract=element["abstract"],
                            balance=element.get("xbrli:balance") if element.get("xbrli:balance") else "")
            xsd_dic[element["id"]] = instance
        return xsd_dic

    @classmethod
    def read_label_taxonomy(cls, reader, xsduri, xsd_dic):
        label_xml = reader.read_by_xsduri(xsduri, 'lab')
        loc_dic = {}
        resource_dic = {}

        def read_label(elem: bs4.element.Tag):
            if elem.name == "loc":
                attrs = elem.attrs

                assert 'xlink:href' in attrs and 'xlink:label' in attrs
                # href  = jpcrp040300-q1r-001_E04251-000_2016-06-30_01_2016-08-12.xsd#jpcrp040300-q1r_E04251-000_ProvisionForLossOnCancellationOfContractEL
                # label = ProvisionForLossOnCancellationOfContractEL
                v = elem['xlink:href'].split('#')
                assert len(v) == 2
                loc_dic[elem['xlink:label']] = v[1]

            elif elem.name == "label":
                attrs = elem.attrs

                if 'xlink:label' in attrs and 'xlink:role' in attrs:
                    label_role = "http://www.xbrl.org/2003/role/label"
                    verboseLabel_role = "http://www.xbrl.org/2003/role/verboseLabel"                    
                    if elem['xlink:role'] in [label_role, verboseLabel_role]:
                        resource_dic[elem['xlink:label']] = {'role': elem['xlink:role'], 'text': elem.text}

                id = elem["id"]
                if id is None:
                    # {http://www.xbrl.org/2003/linkbase}label
                    return
                assert id.startswith("label_")

            elif elem.name == "labelArc":
                attrs = elem.attrs

                if 'xlink:from' in attrs and 'xlink:to' in attrs and elem['xlink:to'] in resource_dic:
                    if elem['xlink:from'] in loc_dic and loc_dic[elem['xlink:from']] in xsd_dic:
                        ele = xsd_dic[loc_dic[elem['xlink:from']]]
                        res = resource_dic[elem['xlink:to']]
                        ele.set_label(**res) # Label(res['role'], res['text'])

            for child in elem.select("*"):
                read_label(child)

        for elem in label_xml.find_all('link:labelLink'):
            read_label(elem)

    def set_label(self, role, text):
        if role.endswith('label'):
            self.label = text
        elif role.endswith('verboseLabel'):
            self.verbose_label = text

    def to_dict(self):
        return {
            "name": self.name,
            "reference": self.reference,
            "label": self.label,
            "abstract": self.abstract,
            "data_type": self.data_type,
            "period_type": self.period_type,
            "balance": self.balance
        }
