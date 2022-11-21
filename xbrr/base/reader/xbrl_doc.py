import os
from datetime import datetime
from xbrr.base.reader.base_doc import BaseDoc
from bs4 import BeautifulSoup

class XbrlDoc(BaseDoc):

    def __init__(self, package, root_dir="", xbrl_file=""):
        super().__init__(package, root_dir=root_dir, xbrl_file=xbrl_file)
        self._cache = {}

        def read_schemaRefs(xsd_xml):
            dict = {}
            schema = xsd_xml.find('schema')
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
        self._schema_dic = read_schemaRefs(xsd_xml) if xsd_xml is not None else None
        self._linkbase_tuples = read_linkbaseRefs(xsd_xml) if xsd_xml is not None else None

    def read_file(self, kind):
        path = self.find_path(kind)
        if (not os.path.isfile(path)):
            return None
        if kind not in self._cache:
            with open(path, encoding="utf-8-sig") as f:
                self._cache[kind] = BeautifulSoup(f, "lxml-xml")
        return self._cache[kind]
    
    def find_laburi(self, xsduri, kind) -> str:
        """find label xml uri by schema uri"""
        namespace = xsduri
        if xsduri.startswith('http'):
            namespace = next(k for k,v in self._schema_dic.items() if v==xsduri)

        href = self._find_linkbaseRef(kind, namespace)
        if len(href) == 0:
            path = self.find_path(kind)
            href = os.path.basename(path)
        return href
    
    def find_xsduri(self, namespace) -> str:
        """find xsd uri by namespace """
        if namespace not in self._schema_dic:
            if namespace.startswith('http'):
                raise LookupError("Unknown namespace: " + namespace)
            # for "local" namespace
            xsdloc = os.path.basename(self.find_path('xsd'))
            return xsdloc
        return self._schema_dic[namespace]

    def _find_linkbaseRef(self, kind, namespace) -> str:
        if namespace.startswith('http'):
        # if namespace!="local":
            ns_base = "/".join(namespace.split('/')[0:-1])
        else:
            ns_base = os.path.basename(os.path.splitext(self.xbrl_file)[0])

        for pair in self._linkbase_tuples:
            if pair[0].startswith(ns_base) and pair[0].endswith(kind+".xml"):
                return pair[0]

        raise Exception(f"linkbase ref does not exist.")