import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup, Tag

from xbrr.base.reader.base_reader import BaseReader

class SchemaTree():
    def __init__(self, reader:BaseReader, base_xsd:str):
        self.reader = reader
        self.base_xsduri = os.path.basename(base_xsd)
        base_namespace = self.get_targetNamespace(self.base_xsduri)
        self.namespace_uri = {}
        self.namespace_uri[base_namespace] = self.base_xsduri
        self.namespace_linkbaseRef = {}
        self.linkbaseRefs = []
        self.read_import_tree(base_namespace, self.base_xsduri)

    def get_targetNamespace(self, xsduri:str):
        xsd_xml = self.reader.read_uri(xsduri)
        schema = xsd_xml.select_one('schema')
        if schema is None:
            return ''
        return str(schema['targetNamespace'])

    def read_import_tree(self, xsd_ns:str, xsduri:str):
        def get_absxsduri(docuri, xsduri):
            if xsduri.startswith('http'): return xsduri
            return urljoin(docuri, xsduri)
        self.namespace_linkbaseRef[xsd_ns] = []

        xsd_xml = self.reader.read_uri(xsduri)
        for ref in xsd_xml.find_all(['import','link:linkbaseRef']):
            if not isinstance(ref, Tag): continue
            if ref.name=='import':
                ref_ns = str(ref['namespace'])
                ref_xsduri = urljoin(xsduri, str(ref['schemaLocation']))
                self.namespace_uri[ref_ns] = ref_xsduri
                self.read_import_tree(ref_ns, ref_xsduri)
            else: # link:linkbaseRef
                # ex.: <link:linkbaseRef xlink:type="simple" xlink:href="jpcrp030000-asr-001_E00436-000_2018-03-31_01_2018-06-26_pre.xml" xlink:role="http://www.xbrl.org/2003/role/presentationLinkbaseRef" xlink:arcrole="http://www.w3.org/1999/xlink/properties/linkbase" />
                linkrole_uri = str(ref.get('xlink:role'))
                linkrole = linkrole_uri.split('/')[-1] if linkrole_uri is not None else ''
                linkbaseRef = (get_absxsduri(xsduri, ref['xlink:href']), linkrole)
                self.namespace_linkbaseRef[xsd_ns].append(linkbaseRef)
                self.linkbaseRefs.append(linkbaseRef)

    def find_kind_uri(self, kind:str, xsduri="") -> str:
        kind2linkbase = {'lab':'labelLinkbaseRef', 'cal':'calculationLinkbaseRef', 
                        'pre':'presentationLinkbaseRef', 'def':'definitionLinkbaseRef'}
        linkbase_type = kind2linkbase[kind]
        if xsduri=="": xsduri = os.path.basename(self.base_xsduri)
        return self._find_linkbaseRef(linkbase_type, xsduri)

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

        return 'no_linkbase_ref.xml'
        raise ImportError('linkbaseRefs Error:{} for {}'.format(doc_base, linkbase_type))

    def presentation_version(self) -> str:
        # 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/ac/edjp/sm/2012-03-31/tse-acedjpsm-2012-03-31-presentation.xml'
        # 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/qc/edjp/sm/2007-06-30/tse-qcedjpsm-2007-06-30-presentation.xml'
        edjp_sm_prefix = 'http://www.xbrl.tdnet.info/jp/br/tdnet/r/'
        for pair in self.linkbaseRefs:
            if pair[1] == 'presentationLinkbaseRef' and\
                pair[0].startswith(edjp_sm_prefix):
                return pair[0].replace(edjp_sm_prefix, '').split('/')[3]
        return ''
