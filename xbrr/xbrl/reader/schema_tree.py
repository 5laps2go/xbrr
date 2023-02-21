import os
from urllib.parse import urljoin

from bs4 import BeautifulSoup


class SchemaTree():
    def __init__(self, reader, base_xsd:str):
        self.reader = reader
        self.base_xsduri = os.path.basename(base_xsd)
        base_namespace = self.get_targetNamespace(self.base_xsduri)
        self.namespace_uri = {}
        self.namespace_uri[base_namespace] = self.base_xsduri
        self.namespace_linkbaseRef = {}
        self.linkbaseRefs = []
        self.read_import_tree(base_namespace, self.base_xsduri)

    def get_targetNamespace(self, xsduri:str) -> str:
        xsd_xml = self.reader.read_uri(xsduri)
        schema = xsd_xml.find('schema')
        if schema is not None:
            return schema['targetNamespace']

    def read_import_tree(self, xsd_ns:str, xsduri:str):
        def get_absxsduri(docuri, xsduri):
            if xsduri.startswith('http'): return xsduri
            return urljoin(docuri, xsduri)
        def read_linkbaseRefs(xsd_xml, xsduri):
            href_list = []
            for ref in xsd_xml.find_all('link:linkbaseRef'):
                # ex.: <link:linkbaseRef xlink:type="simple" xlink:href="jpcrp030000-asr-001_E00436-000_2018-03-31_01_2018-06-26_pre.xml" xlink:role="http://www.xbrl.org/2003/role/presentationLinkbaseRef" xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase" />
                linkrole_uri = ref.get('xlink:role')
                linkrole = linkrole_uri.split('/')[-1] if linkrole_uri is not None else ''
                href_list.append((get_absxsduri(xsduri, ref['xlink:href']), linkrole))
            return href_list

        xsd_xml = self.reader.read_uri(xsduri)
        linkbaseRefs = read_linkbaseRefs(xsd_xml, xsduri)
        self.namespace_linkbaseRef[xsd_ns] = linkbaseRefs
        self.linkbaseRefs.extend(linkbaseRefs)

        for ref in xsd_xml.find_all('import'):
            ref_ns = ref['namespace']
            ref_xsduri = ref['schemaLocation']
            self.namespace_uri[ref_ns] = ref_xsduri
            self.read_import_tree(ref_ns, ref_xsduri)

    def find_kind_uri(self, kind:str, xsduri="") -> str:
        kind2linkbase = {'lab':'labelLinkbaseRef', 'cal':'calculationLinkbaseRef', 
                        'pre':'presentationLinkbaseRef', 'def':'definitionLinkbaseRef'}
        linkbase_type = kind2linkbase[kind]
        try:
            if xsduri=="": xsduri = os.path.basename(self.base_xsduri)
            return self._find_linkbaseRef(linkbase_type, xsduri)
        except Exception:
            return ''

    def linkbaseRef_iterator(self, kind:str):
        kind2linkbase = {'lab':'labelLinkbaseRef', 'cal':'calculationLinkbaseRef', 
                        'pre':'presentationLinkbaseRef', 'def':'definitionLinkbaseRef'}
        linkbase_type = kind2linkbase[kind]
        for pair in self.linkbaseRefs:
            if pair[1] == linkbase_type:
                yield pair[0]

    def find_xsduri(self, namespace:str) -> str:
        """find xsd uri by namespace """
        uri = self.namespace_uri.get(namespace, None)
        if uri is None:
            raise LookupError("Unknown namespace: " + namespace)
        return uri

    def _find_linkbaseRef(self, linkbase_type:str, docuri:str) -> str:
        if docuri.startswith('http'):
            doc_base = os.path.dirname(docuri)
        else: # for local document
            doc_base = os.path.basename(os.path.splitext(docuri)[0])

        for pair in self.linkbaseRefs:
            if pair[0].startswith(doc_base) and pair[1]==linkbase_type:
                if linkbase_type=='labelLinkbaseRef' and pair[0].endswith('-en.xml'):
                    continue
                return pair[0]

        raise Exception(f"linkbase ref does not exist.")

    def presentation_version(self) -> str:
        # 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/ac/edjp/sm/2012-03-31/tse-acedjpsm-2012-03-31-presentation.xml'
        # 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/qc/edjp/sm/2007-06-30/tse-qcedjpsm-2007-06-30-presentation.xml'
        edjp_sm_prefix = 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/'
        for pair in self.linkbaseRefs:
            if pair[1] == 'presentationLinkbaseRef' and\
                pair[0].startswith(edjp_sm_prefix):
                return pair[0].replace(edjp_sm_prefix, '').split('/')[3]
        return ''
