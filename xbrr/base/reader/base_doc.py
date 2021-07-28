class BaseDoc():
    """
    Submitted Document base class
    """

    def __init__(self, package, root_dir="", xbrl_file=""):
        self.package = package
        self.root_dir = root_dir
        self.xbrl_file = xbrl_file
    
    def find_path(self, kind):
        raise NotImplementedError("You have to implement find_path method.")

    def find_xsduri(self, namespace):
        raise NotImplementedError("You have to implement find_xsduri method.")

    @property
    def has_schema(self):
        return self.find_path("xsd") is not None

    @property
    def xbrl(self):
        return self.find_file("xbrl")

    @property
    def xsd(self):
        return self.find_file("xsd")

    @property
    def cal(self):
        return self.find_file("cal")

    @property
    def def_(self):
        return self.find_file("def")

    @property
    def lab(self):
        return self.find_file("lab")

    @property
    def lab_en(self):
        return self.find_file("lab-en")

    @property
    def pre(self):
        return self.find_file("pre")

    @property
    def man(self):
        return self.find_file("man")
