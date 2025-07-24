import datetime
from datetime import timedelta

from xbrr.xbrl.reader.element_schema import ElementSchema


class SchemaDicts():

    def __init__(self):
        self.schema_dicts: dict[str, dict[str, ElementSchema]] = {}
        self.custom_dict: dict[str, ElementSchema] = {}

    def add(self, family:str, schema_dict:dict[str, ElementSchema]):
        if family not in self.schema_dicts.keys():
            self.schema_dicts[family] = schema_dict

    def get_dict(self, xsduri:str, element:str) -> dict[str, ElementSchema]:
        # element: tse-acedjpfr-36450_XXXXX, jpcrp030000-asr_E05739-000_XXXXX
        def isStockCode(code:str):             # 銘柄コード for 130A0 or E05739-000
            return code[0:2].isdigit() and len(code)==5 or code.startswith('E') and len(code)==10
        nsprefix = element.rsplit('_', 1)[0]    # tse-acedjpfr-36450, jpcrp030000-asr_E05739-000
        nsp_code = nsprefix.split('-')[-1] if '_' not in nsprefix else nsprefix.split('_')[-1]   # 36450, E05739-000

        if isStockCode(nsp_code):
            return self.custom_dict
        else:
            for family in self.schema_dicts.keys():
                if family in xsduri:
                    return self.schema_dicts[family]
        raise Exception(f"Unknown schema:{xsduri} provided")
