import os
from xbrr.base.reader.base_doc import BaseDoc
from bs4 import BeautifulSoup

class XbrlDoc(BaseDoc):

    def __init__(self, package, root_dir="", xbrl_file=""):
        super().__init__(package, root_dir=root_dir, xbrl_file=xbrl_file)

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
        self._schema_dic = read_schemaRefs(xsd_xml)
        self._linkbase_tuples = read_linkbaseRefs(xsd_xml)

    def find_file(self, kind, as_xml=True):
        path = self.find_path(kind)
        if (not os.path.isfile(path)):
            return None

        if as_xml:
            xml = None
            with open(path, encoding="utf-8-sig") as f:
                xml = BeautifulSoup(f, "lxml-xml")
            return xml

        return path
    
    def find_xmluri(self, kind, xsduri):
        if kind == 'xsd':
            return xsduri

        namespace = xsduri
        if xsduri.startswith('http'):
            namespace = next(k for k,v in self._schema_dic.items() if v==xsduri)

        href = self._find_linkbaseRef(kind, namespace)
        if len(href) == 0:
            path = self.find_path(kind)
            href = os.path.basename(path)
        return href
    
    def find_xsduri(self, namespace):
        if namespace not in self._schema_dic:
            if namespace.startswith('http'):
                raise LookupError("Unknown namespace: " + namespace)
            # for "local" namespace
            xsdloc = os.path.basename(self.find_path('xsd'))
            return xsdloc
        return self._schema_dic[namespace]

    def _find_linkbaseRef(self, kind, namespace):
        if namespace.startswith('http'):
        # if namespace!="local":
            ns_base = "/".join(namespace.split('/')[0:-2])
        else:
            ns_base = os.path.basename(os.path.splitext(self.xbrl_file)[0])

        for pair in self._linkbase_tuples:
            if pair[0].startswith(ns_base) and pair[0].endswith(kind+".xml"):
                return pair[0]
        return None