from typing import Callable, cast

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from xbrr.base.reader.base_element_value import BaseElementValue
from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_schema import ElementSchema


class ElementValue(BaseElementValue):

    NaN: 'ElementValue'  # type: ignore

    hankaku_dic = str.maketrans('１２３４５６７８９０（）［］','1234567890()[]')

    def __init__(self, name:str, reference="",
                 value:str="", unit="", decimals="",
                 context_ref:dict[str,str]={},
                 lazy_schema:Callable[[], ElementSchema]=lambda:ElementSchema()):
        super().__init__()
        self.name = name
        self.reference = reference
        self.value = value
        self.unit = unit
        self.decimals = decimals
        self.context_ref = context_ref
        self.lazy_schema = lazy_schema

    @property
    def normalized_text(self) -> str:
        return self.normalize(self.html.text)

    @property
    def html(self) -> BeautifulSoup:
        html_text = self.value.strip().replace("&lt;", "<").replace("&gt;", ">") if self.value else ''
        html = BeautifulSoup(html_text, "html.parser")
        return html

    @property
    def context(self) -> str:
        return self.context_ref['id'].split('_')[0]

    @property
    def label(self) -> str:
        attr_name = '_lazy_schema'
        if not hasattr(self, attr_name):
            setattr(self, attr_name, self.lazy_schema())
        return getattr(self, attr_name).label

    @property
    def data_type(self) -> str:
        attr_name = '_lazy_schema'
        if not hasattr(self, attr_name):
            setattr(self, attr_name, self.lazy_schema())
        return getattr(self, attr_name).data_type

    @classmethod
    def create_element_value(cls, reader:BaseReader, xml_el:Tag, context_dic:dict[str,dict[str,str]]) -> 'ElementValue':
        name = xml_el.name
        value = xml_el.text.strip().translate(cls.hankaku_dic)
        unit = ""
        if "unitRef" in xml_el.attrs:
            unit = cast(str,xml_el["unitRef"])

        decimals = ""
        if "decimals" in xml_el.attrs:
            decimals = cast(str,xml_el["decimals"])

        reference = f"{xml_el.namespace}#{xml_el.prefix}_{xml_el.name}"

        context_ref = {}
        if "contextRef" in xml_el.attrs:
            context_id = cast(str,xml_el["contextRef"])
            context_ref = context_dic[context_id]
        
        if xml_el.get("xsi:nil",'')=='true':
            value = 'NaN'

        instance = cls(
            name=name, reference=reference,
            value=value, unit=unit, decimals=decimals,
            context_ref=context_ref,
            lazy_schema=lambda :ElementSchema.create_from_reference(reader, reference),
        )
        return instance

    @classmethod
    def read_xbrl_values(cls, reader:BaseReader, xbrl_doc:BeautifulSoup) -> tuple[dict[str,dict[str,str]],dict[str,list['ElementValue']],dict[str,str]]:
        context_dic = {}
        value_dic = {}
        namespace_dic  = {}

        def read_value(elem, nsdecls):
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
                    if elem.find("xbrli:scenario"):
                        if elem.find("xbrldi:explicitMember"):
                            axisdict = {x["dimension"].split(':')[-1]:x.text.split(':')[-1] for x in elem.find_all("xbrldi:explicitMember")}
                            context_val.update(axisdict)
                        elif elem.find("jpfr-oe:NonConsolidated"):
                            context_val.update({"ConsolidatedOrNonConsolidatedAxis":"NonConsolidatedMember"})
                    context_dic[context_id] = context_val
            elif elem.prefix == 'xbrldi':
                pass
            elif len(context_dic) > 0:
                instance = cls.create_element_value(reader, elem, context_dic)
                name = f"{elem.prefix}_{elem.name}"
                if name not in value_dic:
                    value_dic[name] = []
                value_dic[name].append(instance)
        
        xbrl_xml = cast(Tag,xbrl_doc.find("xbrli:xbrl"))
        nsdecls = xbrl_xml.attrs
        for a in nsdecls:
            if a.startswith("xmlns:"):
                namespace_dic[a.replace("xmlns:", "")] = nsdecls[a]

        for child in xbrl_xml.children:
            if isinstance(child, Tag):
                read_value(child, nsdecls)
        return context_dic, value_dic, namespace_dic
    
    def to_dict(self) -> dict[str,str|bool|None]:
        context_id = self.context_ref['id']
        id_parts = context_id.split("_", 1)
        member = ''
        if len(id_parts) > 1:
            member = "_".join([x.replace("Member","") for x in id_parts[1].split("_") if x!="NonConsolidatedMember"])

        return {
            "name": self.name,
            "reference": self.reference,
            "value": self.value,
            "unit": self.unit,
            "decimals": self.decimals,
            "consolidated": "NonConsolidated" not in context_id,
            "context": id_parts[0],
            "member": member,
            "dimension": ",".join([x for x in self.context_ref.keys() if x.endswith("Axis")]),
            "period": self.context_ref['period'],
            "period_start": self.context_ref['period_start'] if 'period_start' in self.context_ref else None,
            "label": self.label,
        }
        # context string fragment:
        #   CurrentYear	        当年度
        #   Interim	            中間期
        #   Prior1Year	        前年度
        # 	Prior1Interim	    前中間期
        # 	Prior2Year	        前々年度
        #   Prior2Interim	    前々中間期
        #   Prior{n}Year	    {n}年度前
        #   Prior{n}Interim	    {n}年度前中間期
        #   CurrentYTD	        当四半期累計期間
        # 	CurrentQuarter	    当四半期会計期間
        # 	Prior{n}YTD	        {n}年度前同四半期累計期間
        # 	Prior{n}Quarter	    {n}年度前同四半期会計期間
        #   NextYear            翌年度
        #   NextAccumulatedQ2   翌第2四半期（累計）
        # 	FilingDate	        提出日
        # 	RecordDate	        議決権行使の基準日
        # 	RecentDate	        最近日
        # 	FutureDate	        予定日
        # 	Instant	            時点
        # 	Duration	        期間
        # 	Consolidated        連結会計        for old xbrl
        #   NonConsolidated     非連結会計      for old xbrl
        # consolidated
        #   True                連結会計
        #   False               非連結会計
        # member examples:
        #   LegalCapitalSurplusMember CapitalStockMember RetainedEarningsMember CapitalSurplusMember
        #   PreviousMember_ForecastMember   前回発表予想
        #   CurrentMember_ForecastMember    今回修正予想
        # dimension:
        #   jpcrp_cor:OperatingSegmentsAxis      セグメント
        #   jpigp_cor:ComponentsOfEquityIFRSAxis EquityIFRS詳細


ElementValue.NaN = ElementValue('NaN', value='NaN') # ElementValue that holds 'NaN' value
