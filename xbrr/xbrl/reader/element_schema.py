import os

import bs4
from bs4.element import NavigableString, Tag

from xbrr.base.reader.base_element_schema import BaseElementSchema


class ElementSchema(BaseElementSchema):

    def __init__(self,
                 name="", reference="", label="", alias="",
                 abstract="", data_type="",
                 period_type="", balance=""):
        super().__init__()
        self.name = name
        self.reference = reference
        self.label = label
        self.alias = alias
        self.abstract = abstract
        self.period_type = period_type
        self.balance = balance
        self.verbose_label = ""

        # data types:
        #  domain, textBlock, percent, perShare, boolean, date, decimal,
        #  monetary, nonNegativeInteger, shares, string
        self.data_type = data_type
        if data_type is not None and ':' in data_type:
            self.data_type = data_type.split(':')[-1].replace('ItemType','')

    def set_alias(self, alias):
        self.alias = alias
        return self

    @classmethod
    def create_from_reference(cls, reader, reference) -> 'ElementSchema':
        if not reader.xbrl_doc.has_schema: # for test purpose only
            name = reference.split("#")[-1]
            instance = cls(name=name, reference=reference)
            return instance

        instance = reader.get_schema_by_link(reference)
        instance.reference = reference
        return instance


    @classmethod
    def read_schema(cls, reader, xsduri):
        def find_labelLinkbaseRef(xsduri, xsd_xml):
            base = os.path.splitext(os.path.basename(xsduri))[0]
            for linkbaseref in xml.find_all("linkbaseRef"):
                role = linkbaseref.get("xlink:role",'')
                href = linkbaseref["xlink:href"]
                if role.endswith("/labelLinkbaseRef") and base in href and not href.endswith("-en.xml"):
                    if not href.startswith('http') and xsduri.startswith('http'):
                        return os.path.dirname(xsduri) + "/" + href
                    return href
            return ''
        xsd_dic = {}
        xml = reader.read_uri(xsduri)
        for element in xml.find_all("element"):
            # <xsd:element id="jpcrp030000-asr_E00436-000_Subsidy" xbrli:balance="credit" xbrli:periodType="duration" abstract="false" name="Subsidy" nillable="true" substitutionGroup="xbrli:item" type="xbrli:monetaryItemType" />
            instance = cls(name=element["id"], alias=element["name"], 
                            data_type=element["type"], 
                            period_type=element["xbrli:periodType"],
                            abstract=element["abstract"] if element.get("abstract") else "",
                            balance=element.get("xbrli:balance") if element.get("xbrli:balance") else "")
            xsd_dic[element["id"]] = instance

        laburi = find_labelLinkbaseRef(xsduri, xml)
        if laburi:
            cls.read_label_taxonomy(reader, laburi, xsd_dic)
        else:
            laburi = reader.get_label_uri(xsduri)
            cls.read_label_taxonomy(reader, laburi, xsd_dic)
        return xsd_dic

    @classmethod
    def read_label_taxonomy(cls, reader, laburi, xsd_dic):
        label_xml = reader.read_uri(laburi)
        loc_dic = {}
        resource_dic = {}

        def read_label_loc(elem: bs4.element.Tag):
            attrs = elem.attrs

            assert 'xlink:href' in attrs and 'xlink:label' in attrs
            # href  = jpcrp040300-q1r-001_E04251-000_2016-06-30_01_2016-08-12.xsd#jpcrp040300-q1r_E04251-000_ProvisionForLossOnCancellationOfContractEL
            # label = ProvisionForLossOnCancellationOfContractEL
            v = elem['xlink:href'].split('#')  # type: ignore
            assert len(v) == 2
            loc_dic[elem['xlink:label']] = v[1]

        def read_label_label(elem: bs4.element.Tag):
            attrs = elem.attrs

            if 'xlink:label' in attrs and 'xlink:role' in attrs:
                label_role = "http://www.xbrl.org/2003/role/label"
                verboseLabel_role = "http://www.xbrl.org/2003/role/verboseLabel"                    
                if elem['xlink:role'] in [label_role, verboseLabel_role]\
                    and elem['xlink:label'] not in resource_dic:
                    resource_dic[elem['xlink:label']] = {'role': elem['xlink:role'], 'text': elem.text}

        def read_label_labelArc(elem: bs4.element.Tag):
            attrs = elem.attrs

            if 'xlink:from' in attrs and 'xlink:to' in attrs and elem['xlink:to'] in resource_dic:
                if elem['xlink:from'] in loc_dic and loc_dic[elem['xlink:from']] in xsd_dic:
                    ele = xsd_dic[loc_dic[elem['xlink:from']]]
                    res = resource_dic[elem['xlink:to']]
                    ele.set_label(**res) # Label(res['role'], res['text'])

        for elem in label_xml.find_all('labelLink'): # "link:labelLink"
            for child in elem.find_all('loc'):
                read_label_loc(child)
            for child in elem.find_all('label'):
                read_label_label(child)
            for child in elem.find_all('labelArc'):
                read_label_labelArc(child)

    def set_label(self, role, text):
        if role.endswith('label'):
            self.label = text.strip()
        elif role.endswith('verboseLabel'):
            self.verbose_label = text.strip()

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
