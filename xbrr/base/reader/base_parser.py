import re
import datetime
import unicodedata


class BaseParser():
    """
    Element to Value
    """

    def __init__(self, reader, value_class, tags=()):
        self.reader = reader
        self.value_class = value_class
        self.tags = {}
        if len(tags) > 0:
            self.tags = tags
            
    def __getattr__(self, name):
        if name in self.tags.keys():
            return self.get_value(name)
        raise NameError(name)

    def normalize(self, text):
        if text is None:
            return ""
        _text = text.strip()
        _text = unicodedata.normalize("NFKC", _text)
        return _text

    def get_value(self, name):
        value = self.reader.findv(self.tags[name])
        if not value:
            return self.value_class(self.tags[name], value=None)
        return value

    def search(self, name, pattern):
        value = self.reader.findv(self.tags[name])
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

    def extract_value(self, name, prefix="", suffix="",
                      filter_pattern=None):
        value = self.reader.findv(self.tags[name])
        text = value.html.text
        if filter_pattern is not None:
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
