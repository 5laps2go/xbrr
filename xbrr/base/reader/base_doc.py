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

    def read_file(self, kind):
        raise NotImplementedError("You have to implement read_file method.")

    def find_xsduri(self, namespace):
        raise NotImplementedError("You have to implement find_xsduri method.")

    def create_taxonomies(self, root_dir):
        raise NotImplementedError("You have to implement create_taxonomies method.")

    @property
    def published_date(self):
        raise NotImplementedError("You have to implement published_date.")
    
    @property
    def company_code(self):
        raise NotImplementedError("You have to implement company_code.")
    
    @property
    def default_linkbase(self):
        raise NotImplementedError("You have to implement default_linkbase.")
        
    @property
    def has_schema(self):
        return self.find_path("xsd") is not None

    @property
    def xbrl(self):
        return self.read_file("xbrl")

    @property
    def xsd(self):
        return self.read_file("xsd")

    @property
    def cal(self):
        return self.read_file("cal")

    @property
    def def_(self):
        return self.read_file("def")

    @property
    def lab(self):
        return self.read_file("lab")

    @property
    def lab_en(self):
        return self.read_file("lab-en")

    @property
    def pre(self):
        return self.read_file("pre")

    @property
    def man(self):
        return self.read_file("man")
