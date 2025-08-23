import errno
import glob
import os
import re
from datetime import datetime
from typing import cast

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag, PageElement

from xbrr.base.reader.xbrl_doc import XbrlDoc


class Doc(XbrlDoc):

    def __init__(self, root_dir="", xbrl_kind=""):

        def _glob_list(patterns):
            for patn in patterns:
                xsd_files = glob.glob(os.path.join(root_dir, patn), recursive=True)
                if xsd_files: return xsd_files
            return []
        def _xbrl_file(root_dir, kind):
            patn_dict = {'public': ['**/tse-??????fr-*.xsd', '**/tdnet-??????fr-*.xsd'],
                         'summary': ['**/tse-??????s[my]-*.xsd','**/tse-rv??-*.xsd','**/tdnet-??????sm-*.xsd']}
            xsd_files = _glob_list(patn_dict[kind])
            if not xsd_files:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), patn_dict[kind])
            xbrl_file = self._prepare_xbrl(sorted(xsd_files,reverse=True)[0])
            return xbrl_file
        
        xbrl_file=_xbrl_file(root_dir, xbrl_kind)
        self.xbrl_kind = xbrl_kind
        self.file_spec = os.path.splitext(xbrl_file)[0]
        super().__init__("tdnet", root_dir=root_dir, xbrl_file=xbrl_file)

    @staticmethod
    def find_report(root_dir: str) -> "Doc":
        try:
            doc = Doc(root_dir=root_dir, xbrl_kind='summary')
        except FileNotFoundError as e:
            doc = Doc(root_dir=root_dir, xbrl_kind='public')
        return doc

    def find_path(self, kind) -> str:
        # TDNET report file name spec. is like EDINET
        # around 2014, -calculation.xml,-presentation.xml after 2020 -cal.xml,-pre.xml
        suffix = {
            "xbrl": ".xbrl", "xsd": ".xsd",
            # "cal": "-cal*.xml", "def": "-def.xml",
            # "lab": "-lab.xml", "lab-en": "-lab-en.xml", "pre": "-pre*.xml",
            }

        if kind == "man":
            path = os.path.join(os.path.dirname(self.file_spec), "manifest.xml")
            if len(path)==0:
                raise Exception(f"manifest file does not exist.")
        elif kind in suffix:
            path = self.file_spec + suffix[kind]
            files = glob.glob(path)
            if len(files)>0: return files[0]
        else: # kind=file name case
            path = os.path.join(os.path.dirname(self.file_spec), kind)

        return path

    @property
    def default_linkbase(self) -> dict[str, str]:
        if 'public' == self.xbrl_kind:
            return {
                'doc': 'pre', # document kind for the order of financial statements
                'link_node': 'presentationLink',
                'arc_node': 'presentationArc',
                'roleRef': 'roleRef',
                'arc_role': 'parent-child'
            }

        assert self.xbrl_kind == 'summary'
        if '/tse-' in self.file_spec:
            return {
                'doc': 'def', # document kind for the order of financial statements
                'link_node': 'definitionLink',
                'arc_node': 'definitionArc',
                'roleRef': 'roleRef',
                'arc_role': 'domain-member'
            }

        assert '/tdnet-' in self.file_spec # old type of taxonomy before 2014
        return {
            'doc': 'pre', # document kind for the order of financial statements
            'link_node': 'presentationLink',
            'arc_node': 'presentationArc',
            'roleRef': 'roleRef',
            'arc_role': 'parent-child'
        }

    @property
    def published_date(self) -> tuple[datetime, str]:
        if 'public' == self.xbrl_kind:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            date = datetime.strptime("%s-%s-%s" % (v[7], v[8], v[9]), "%Y-%m-%d")
            period = v[1][0]
            return date, period
        elif 'summary' == self.xbrl_kind:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            date = datetime.strptime("%s-%s-%s" % (v[3][:4], v[3][4:6], v[3][6:8]), "%Y-%m-%d")
            period = v[1][0]
            return date, period
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    @property
    def report_period_end_date(self) -> datetime:
        if 'public' == self.xbrl_kind:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            date = datetime.strptime("%s-%s-%s" % (v[3], v[4], v[5]), "%Y-%m-%d")
            return date
        # elif 'summary' == self.xbrl_kind:
        #     # Summary/tse-acedjpsm-36450-20210714336450
        #     #          0      1       2         3 
        #     v = os.path.basename(self.file_spec).split('-')
        #     date = datetime.strptime(v[3][0:8], "%Y%m%d")
        #     return date
        else:
            raise LookupError("Fiscal year date is not encoded")

    @property
    def company_code(self) -> str:
        if 'public' == self.xbrl_kind:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            return v[2]
        elif 'summary' == self.xbrl_kind:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            return v[2]
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    @property
    def consolidated(self) -> bool:
        def test_consolidated(c) -> bool:
            return True if c=='c' else False
        if 'public' == self.xbrl_kind:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            return test_consolidated(v[1][1])
        elif 'summary' == self.xbrl_kind:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            if v[1] in ['rrfc','rvfc','rvdf']:  # rrfc	配当金修正, rvfc	業績予想修正, rvdf	配当予想のお知らせ
                raise LookupError("no information for consolidated identification")
            return test_consolidated(v[1][1])
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    @property
    def accounting_standard(self) -> str:
        if 'public' == self.xbrl_kind:
            # Attachment/tse-acedjpfr-36450-2021-05-31-01-2021-07-14
            #             0  1          2     3   4  5  6   7   8  9
            v = os.path.basename(self.file_spec).split('-')
            return v[1][4:6] if len(v[1])==8 else ''
        elif 'summary' == self.xbrl_kind:
            # Summary/tse-acedjpsm-36450-20210714336450
            #          0      1       2         3 
            v = os.path.basename(self.file_spec).split('-')
            if v[1] in ['rrfc','rvfc','rvdf']:  # rrfc	配当金修正, rvfc	業績予想修正, rvdf	配当予想のお知らせ
                return ''
            return v[1][4:6] if len(v[1])==8 else ''
        else:
            raise FileNotFoundError("No Attachment or Summary folder found.")

    @property
    def xbrl(self) -> BeautifulSoup:
        if os.path.isfile(self.xbrl_file) and os.path.getsize(self.xbrl_file)>0:
            return super().read_file('xbrl')
        return self.read_ixbrl_as_xbrl()

    def _prepare_xbrl(self, xsd_file: str) -> str:
        """process ixbrl to xbrl
        """
        if not os.path.isfile(xsd_file):
            raise Exception(f"XSD file does not exist.")
        # xsl_file = "/usr/local/share/inlinexbrl/processor/Main_exslt.xsl"

        self.file_spec = os.path.splitext(xsd_file)[0]
        manifest_file = self.find_path('man')
        if os.path.isfile(manifest_file):
            infile = manifest_file
            with open(manifest_file, encoding="utf-8-sig") as f:
                manifest_xml = BeautifulSoup(f, "lxml-xml")
            instance_tag = manifest_xml.select_one('instance')
            if not instance_tag:
                return self.file_spec + ".xbrl"
            xbrl_file = os.path.join(os.path.dirname(self.file_spec),
                                     str(instance_tag['preferredFilename']))
        else:
            infile = self.file_spec+"-ixbrl.htm"
            xbrl_file = self.file_spec + ".xbrl"
        return xbrl_file

    def read_ixbrl_as_xbrl(self) -> BeautifulSoup:
        def clone(el):
            if isinstance(el, NavigableString):
                return type(el)(el)
            copy = Tag(None, el.builder, el.name, el.namespace, el.prefix)
            # work around bug where there is no builder set
            # https://bugs.launchpad.net/beautifulsoup/+bug/1307471
            copy.attrs = dict(el.attrs)
            for attr in ('can_be_empty_element', 'hidden'):
                setattr(copy, attr, getattr(el, attr))
            for child in el.contents:
                copy.append(clone(child))
            return copy        
        def xlate_to_xbrl(element, xbrl_xml, separator, outbs):
            scale_hist:dict[int,int] = {}
            def __new_ixvalue(name, prefix, attrs, value):
                xbrli = outbs.new_tag(name, namespace=nsdecls['xmlns:'+prefix], nsprefix=prefix, **attrs)
                xbrli.string = value
                xbrl_xml.append(xbrli)
            def __replace_nonXXX_on_src(element):
                # replace ix:nonXXX to its string on ixbrl tree
                if not element.contents:
                    element.extract()
                else:
                    element.replace_with(element.contents[0].extract())
            def __xlate_to_xbrl(element):
                def previous_tagstr(elem) -> str:
                    if bool(re.search('[0-9]',elem.previous_sibling.string or '')):
                        return elem.previous_sibling.string
                    for e in elem.previous_siblings:
                        if isinstance(e, Tag): return e.text
                    return ''
                if isinstance(element, NavigableString): return
                for elem in list(element.contents):  # list not to skip by elem.extract()
                    if not isinstance(elem, Tag): continue
                    if elem.prefix == 'ix':
                        if elem.name in ['nonNumeric']:
                            prefix,name = tuple(str(elem["name"]).split(':'))
                            attrs = {k:v for k,v in elem.attrs.items() 
                                    if k in ['contextRef','decimals','unitRef','xsi:nil']}
                            __xlate_to_xbrl(elem)
                            value = str(elem) if elem.attrs.get("escape", "false")=="true" else elem.text
                            __new_ixvalue(name, prefix, attrs, value)
                            __replace_nonXXX_on_src(elem)
                            continue
                        elif elem.name in ['nonFraction', 'nonfraction']:
                            prefix,name = tuple(str(elem["name"]).split(':'))
                            value = elem.text
                            attrs = {k:v for k,v in elem.attrs.items() 
                                    if k in ['contextRef','decimals','unitRef','xsi:nil']}
                            if "scale" in elem.attrs and elem.attrs.get("format",'ixt:numdotdecimal')=='ixt:numdotdecimal': # no format case:3276:2014-02-10
                                scale = int(str(elem.attrs["scale"]))
                                decimals = int(str(elem.attrs["decimals"]))
                                if elem.get('unitRef') in ['JPY','USD']:
                                    scale_hist[scale] = scale_hist.get(scale,0) + 1
                                    if len(scale_hist) > 1: # scale bug 6578:2019-07-11
                                        scale = max(scale_hist, key=scale_hist.get) # type: ignore
                                        decimals = -scale
                                try:
                                    # temporary fix for bad ix format
                                    if value=='':
                                        m = re.search(r'[0-9,.]+', previous_tagstr(elem))
                                        if not m: continue
                                        value = m.group()
                                    
                                    fval = float(value.replace(',','')) * 10**scale
                                except ValueError:  # case '0.0<br/>'
                                    value = re.sub("<.*>", "", value)
                                    fval = float(value.replace(',','')) * 10**scale
                                if "sign" in elem.attrs:
                                    fval = -fval
                                value = '{0:.{1}f}'.format(fval, decimals if decimals>0 else 0)
                            __new_ixvalue(name, prefix, attrs, value)
                            __replace_nonXXX_on_src(elem)
                            continue
                        elif elem.name in ['references', 'resources']:
                            for xbrli in elem.children:
                                separator.insert_before(clone(xbrli))
                            continue
                        # elem.name in ['header', 'hidden']:
                    # not ix prefix
                    __xlate_to_xbrl(elem)
            nsdecls = xbrl_xml.attrs
            __xlate_to_xbrl(element)
        def translate_ixbrl(infile, outbs):
            with open(infile, encoding="utf-8-sig") as f:
                ixbrl = BeautifulSoup(f, "lxml-xml")

            ixbrl_html = ixbrl.find("html")
            xbrl_xml = outbs.find('xbrli:xbrl')
            if not xbrl_xml:
                assert isinstance(ixbrl_html, Tag)
                nsdecls = {k:v for k,v in ixbrl_html.attrs.items() if ':' in k and k!='xmlns:ix'}
                xbrl_xml = outbs.new_tag('xbrli:xbrl', **nsdecls)
                outbs.append(xbrl_xml)
                xbrl_xml.append(outbs.new_tag('separator'))
            separator = xbrl_xml.find('separator')
            xlate_to_xbrl(ixbrl_html, xbrl_xml, separator, outbs)
                    
        xbrlbs = BeautifulSoup("", "lxml-xml")
        manifest_file = self.find_path('man')
        if os.path.isfile(manifest_file):
            infile = manifest_file
            with open(manifest_file, encoding="utf-8-sig") as f:
                manifest_xml = BeautifulSoup(f, "lxml-xml")
            instance_tag = manifest_xml.find('instance')
            assert isinstance(instance_tag, Tag)
            for ixbrl in instance_tag.children:
                if isinstance(ixbrl, Tag) and ixbrl.name=="ixbrl":
                    infile = os.path.join(os.path.dirname(self.file_spec), str(ixbrl.string))
                    translate_ixbrl(infile, xbrlbs)
        else:
            infile = self.file_spec+"-ixbrl.htm"
            translate_ixbrl(infile, xbrlbs)
        cast(Tag,xbrlbs.find('separator')).extract() # remove supporting tag
        return xbrlbs
