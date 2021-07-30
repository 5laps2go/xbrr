from xbrr.base.reader.base_element_value import BaseElementValue
from xbrr.edinet.reader.element_schema import ElementSchema
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


class ElementValue(BaseElementValue):

    def __init__(self, name="", reference="",
                 value="", unit="", decimals="",
                 context_ref={},
                 lazy_schema=None):
        super().__init__()
        self.name = name
        self.reference = reference
        self.value = value
        self.unit = unit
        self.decimals = decimals
        self.context_ref = context_ref
        self.lazy_schema = lazy_schema

    @property
    def normalized_text(self):
        return self.normalize(self.html.text)

    @property
    def html(self):
        html_text = self.value.strip().replace("&lt;", "<").replace("&gt;", ">")
        html = BeautifulSoup(html_text, "html.parser")
        return html

    @property
    def context(self):
        return self.context_ref['id'].split('_')[0]

    @property
    def label(self):
        attr_name = '_lazy_schema'
        if not hasattr(self, attr_name):
            setattr(self, attr_name, self.lazy_schema())
        return getattr(self, attr_name).label

    @classmethod
    def create_element_value(cls, reader, xml_el, context_dic):

        name = xml_el.name
        value = xml_el.text
        unit = ""
        if "unitRef" in xml_el.attrs:
            unit = xml_el["unitRef"]

        decimals = ""
        if "decimals" in xml_el.attrs:
            decimals = xml_el["decimals"]

        xsduri = reader.xbrl_doc.find_xsduri(xml_el.namespace)
        reference = f"{xsduri}#{xml_el.prefix}_{xml_el.name}"

        if "contextRef" in xml_el.attrs:
            context_id = xml_el["contextRef"]
            context_ref = context_dic[context_id]

        instance = cls(
            name=name, reference=reference,
            value=value, unit=unit, decimals=decimals,
            context_ref=context_ref,
            lazy_schema=lambda :ElementSchema.create_from_reference(reader, reference),
        )
        return instance

    @classmethod
    def read_xbrl_values(cls, reader, xbrl_doc):
        context_dic = {}
        value_dic = {}
        namespace_dic  = {}

        def read_value(elem):
            if elem.prefix == 'link':
                pass
            elif elem.prefix == 'xbrli':
                if elem.name == 'context':
                    context_id = elem["id"]
                    context_val = {}
                    if elem.find("xbrli:instant"):
                        period = elem.find("xbrli:instant").text
                        context_val = {'id': context_id, 'period': period}
                    elif elem.find("xbrli:endDate"):
                        period = elem.find("xbrli:endDate").text
                        period_start = elem.find("xbrli:startDate").text
                        context_val = {'id': context_id, 'period': period, 'period_start': period_start}
                    context_dic[context_id] = context_val
            elif elem.prefix == 'xbrldi':
                pass
            else:
                instance = cls.create_element_value(reader, elem, context_dic)
                name = f"{elem.prefix}_{elem.name}"
                if name not in value_dic:
                    value_dic[name] = [instance]
                else:
                    value_dic[name].append(instance)
        
        xbrl_xml = xbrl_doc.find("xbrli:xbrl")
        nsdecls = xbrl_xml.attrs
        for a in nsdecls:
            if a.startswith("xmlns:"):
                namespace_dic[a.replace("xmlns:", "")] = nsdecls[a]

        for child in xbrl_xml.children:
            if isinstance(child, Tag):
                read_value(child)
        return context_dic, value_dic, namespace_dic
    
    @classmethod
    def read_finance_statement(cls, reader, statement_xml):
        class dotdict(dict):
            """dot.notation access to dictionary attributes"""
            __getattr__ = dict.get
            __setattr__ = dict.__setitem__
            __delattr__ = dict.__delitem__

        def myen(value):
            if value=='－':
                return '000'
            myen = value.replace(',','').replace('△', '-')
            return myen
        def isnum(myen):
            try:
                float(myen)
            except ValueError:
                return False
            else:
                return True

        unit = ''
        values = []
        for table in statement_xml.select('table'):
            for record in table.select('tr'):
                columns = list(record.select('td'))
                label = columns[0].text.strip()
                value = myen(columns[-1].text.strip())
                if isnum(value):
                    # lazy_schema = lambda : dotdict({'label': label})
                    # context_ref = {}
                    values.append((label, value+unit))
                else:
                    assert value=='' or '単位：' in value or '当連結会計年度' in value
                    if '単位：百万円' in value:
                        unit = '000000'
                    elif '単位：円' in value:
                        unit = ''
        return values

    def to_dict(self):
        context_id = self.context_ref['id']
        id_parts = context_id.split("_", 1)

        return {
            "name": self.name,
            "reference": self.reference,
            "value": self.value,
            "unit": self.unit,
            "decimals": self.decimals,
            "consolidated": "NonConsolidatedMember" not in context_id,
            "context": id_parts[0],
            "member": id_parts[1] if len(id_parts) > 1 else '',
            "period": self.context_ref['period'],
            "period_start": self.context_ref['period_start'] if 'period_start' in self.context_ref else None,
            "label": self.label,
        }
