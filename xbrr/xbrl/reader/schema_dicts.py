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
        nsprefix = element.rsplit('_', 1)[0]    # tse-acedjpfr-36450, jpcrp030000-asr_E05739-000
        nsp_suf = nsprefix.split('-')[-1]   # 36450

        if nsp_suf.isdigit():
            return self.custom_dict
        else:
            for family in self.schema_dicts.keys():
                if family in xsduri:
                    return self.schema_dicts[family]
        raise Exception(f"Unknown schema:{xsduri} provided")
