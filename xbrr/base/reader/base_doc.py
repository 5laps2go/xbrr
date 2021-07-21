class BaseDoc():
    """
    Submitted Document base class
    """

    def __init__(self, package, root_dir="", xbrl_file=""):
        self.package = package
        self.root_dir = root_dir
        self.xbrl_file = xbrl_file

    def _find_file(self, link):
        raise NotImplementedError("You have to implement _find_file method.")

    @property
    def has_schema(self):
        return self._find_file("xsd", as_xml=False) is not None

    @property
    def xbrl(self):
        return self._file_file("xbrl")

    @property
    def xsd(self):
        return self._find_file("xsd")

    @property
    def cal(self):
        return self._find_file("cal")

    @property
    def def_(self):
        return self._find_file("def")

    @property
    def lab(self):
        return self._find_file("lab")

    @property
    def lab_en(self):
        return self._find_file("lab-en")

    @property
    def pre(self):
        return self._find_file("pre")

    @property
    def man(self):
        return self._find_file("man")
