import os
from datetime import datetime

from bs4 import BeautifulSoup

from xbrr.base.reader.base_doc import BaseDoc


class XbrlDoc(BaseDoc):

    non_explicit_schema_dict = {
        # TDNET
        "http://www.xbrl.tdnet.info/jp/br/tdnet/t/ed/2007-06-30": "http://www.xbrl.tdnet.info/jp/br/tdnet/t/ed/2007-06-30/tse-t-ed-2007-06-30.xsd",
        # EDINET
        "http://info.edinet-fsa.go.jp/jp/fr/gaap/t/cte/2013-03-01":"http://info.edinet-fsa.go.jp/jp/fr/gaap/t/cte/2013-03-01/jpfr-t-cte-2013-03-01.xsd",
    }

    def __init__(self, package, root_dir="", xbrl_file=""):
        super().__init__(package, root_dir=root_dir, xbrl_file=xbrl_file)
        self._cache = {}

        def read_schemaRefs(xsd_xml):
            dict = {}
            schema = xsd_xml.find('schema')
            if schema is not None:
                dict[schema['targetNamespace']] = os.path.basename(self.find_path('xsd'))
                for ref in xsd_xml.find_all('import'):
                    dict[ref['namespace']] = ref['schemaLocation']
            return dict
        def read_linkbaseRefs(xsd_xml):
            href_list = []
            for ref in xsd_xml.find_all('link:linkbaseRef'):
                # ex.: <link:linkbaseRef xlink:type="simple" xlink:href="jpcrp030000-asr-001_E00436-000_2018-03-31_01_2018-06-26_pre.xml" xlink:role="http://www.xbrl.org/2003/role/presentationLinkbaseRef" xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase" />
                linkrole = ref.get('xlink:role')
                linkrole = linkrole.split('/')[-1] if linkrole is not None else ''
                href_list.append((ref['xlink:href'], linkrole))
            return href_list
        xsd_xml = self.xsd
        self._schema_dic = self.non_explicit_schema_dict
        self._schema_dic.update(read_schemaRefs(xsd_xml))
        self._linkbase_tuples = read_linkbaseRefs(xsd_xml)

    def read_file(self, kind:str) -> BeautifulSoup:
        path = self.find_path(kind)
        if (not os.path.isfile(path)):
            return BeautifulSoup()  # no content
        if kind not in self._cache:
            with open(path, encoding="utf-8-sig") as f:
                self._cache[kind] = BeautifulSoup(f, "lxml-xml")
        return self._cache[kind]

    def find_kind_uri(self, kind:str, xsduri="") -> str:
        kind2linkbase = {'lab':'labelLinkbaseRef', 'cal':'calculationLinkbaseRef', 
                        'pre':'presentationLinkbaseRef', 'def':'definitionLinkbaseRef'}
        linkbase_type = kind2linkbase[kind]
        try:
            if xsduri=="": xsduri = os.path.basename(self.xbrl_file)
            return self._find_linkbaseRef(linkbase_type, xsduri)
        except Exception:
            return ''

    def find_xsduri(self, namespace:str) -> str:
        """find xsd uri by namespace """
        if namespace not in self._schema_dic:
            if namespace.startswith('http'):
                raise LookupError("Unknown namespace: " + namespace)
            # for "local" namespace
            xsdloc = os.path.basename(self.find_path('xsd'))
            return xsdloc
        return self._schema_dic[namespace]

    def _find_linkbaseRef(self, linkbase_type:str, docuri:str) -> str:
        if docuri.startswith('http'):
            doc_base = os.path.dirname(docuri)
        else: # for local document
            doc_base = os.path.basename(os.path.splitext(self.xbrl_file)[0])

        for pair in self._linkbase_tuples:
            if pair[0].startswith(doc_base) and pair[1]==linkbase_type:
                if linkbase_type=='labelLinkbaseRef' and pair[0].endswith('-en.xml'):
                    continue
                return pair[0]

        raise Exception(f"linkbase ref does not exist.")