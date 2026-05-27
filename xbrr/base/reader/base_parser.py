from typing import Optional

import re
import unicodedata
from datetime import datetime, date, timedelta
from logging import getLogger

from xbrr.base.reader.base_reader import BaseReader
from xbrr.xbrl.reader.element_value import ElementValue


class BaseParser():
    """
    Element to Value
    """

    def __init__(self, reader:BaseReader, value_class:type[ElementValue], tags:dict[str,str]={}):
        self.reader = reader
        self.value_class = value_class
        self.tags = {}
        if len(tags) > 0:
            self.tags = tags

        self.logger = getLogger(__name__)
            
    def __getattr__(self, name:str) -> Optional[ElementValue]:
        if name in self.tags.keys():
            return self.get_value(name)
        raise NameError(name)

    def normalize(self, text:str) -> str:
        if text is None:
            return ""
        _text = text.strip()
        _text = unicodedata.normalize("NFKC", _text)
        return _text

    def get_value(self, name:str) -> Optional[ElementValue]:
        value = self.reader.findv(self.tags[name])
        return value

    def search(self, name:str, pattern:str) -> str:
        value = self.reader.findv(self.tags[name])
        if not value:
            return ''
        ptn = re.compile(pattern)
        tags = value.html.find_all(["p", "span"])
        text = ""
        if tags and len(tags) > 0:
            for e in tags:
                _text = self.normalize(e.text)
                match = re.search(ptn, _text)
                if match:
                    text = _text
                    break

        return text

    def extract_value(self, name, prefix:str="", suffix:str="",
                      filter_pattern:str="") -> int|float|str:
        value = self.reader.findv(self.tags[name])
        if not value:
            return ''
        text = value.html.text
        if filter_pattern:
            text = self.search(name, filter_pattern)

        pattern = re.compile(f"({prefix}).+?({suffix})")
        match = re.search(pattern, text)
        value = ""

        if match:
            matched = match[0]
            value = matched.replace(prefix, "").replace(suffix, "")
            value = value.strip()
            if value.isdigit():
                value = int(value)
            elif value.replace(".", "").replace("．", "").isdigit():
                value = float(value)

        return value

    @property
    def fiscal_year_end_date(self) -> date:
        raise NotImplementedError("You have to implement fiscal_year_end_date.")

    @property
    def fiscal_year_start_date(self) -> date:
        raise NotImplementedError("You have to implement fiscal_year_start_date.")
    
    def _get_fiscal_year_start_date_from_context(self) -> date:
        """
        Get fiscal year start date from context information
        """
        def get_start_days(d) -> tuple[date, int, date]:
            start = datetime.strptime(d['period_start'], "%Y-%m-%d").date()
            end = datetime.strptime(d['period'], "%Y-%m-%d").date()
            duration = end - start
            months = min(round(duration.days / 30.44), 12)
            return start, months, end
        fyed = self.fiscal_year_end_date
        durations = [get_start_days(duration) for duration in self.reader.context_dic.values()
                     if 'period_start' in duration and duration['period']<=fyed.isoformat()]
        if not durations:
            self.logger.warning("No duration contexts found.")
            return fyed
        fysd = sorted(durations, key=lambda x: (x[2],x[1],x[0]), reverse=True)[0][0]
        return fysd


