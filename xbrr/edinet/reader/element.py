import os
from xbrr.base.reader.base_element import BaseElement
from xbrr.edinet.reader.element_value import ElementValue


class Element(BaseElement):

    def __init__(self, name, element, reference, reader):
        super().__init__(name, element, reference, reader)
        self.name = name
        self.element = element
        self.reference = reference
        self.reader = reader

    def value(self, label_kind="", label_verbose=False):
        return ElementValue.create_from_element(
                reader=self.reader, element=self,
                label_kind=label_kind, label_verbose=label_verbose)

