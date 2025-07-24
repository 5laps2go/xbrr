from pit import Pit

class BaseClient():
    """"Base API Client.

    Manage the URL and version for the all client.
    """
    BASE_URL = "https://api.edinet-fsa.go.jp/api/{}/{}"

    def __init__(self, target: str, version: str = "v2"):
        """
        Arguments:
            target -- API destination (set by subclass).

        Keyword Arguments:
            version {str} -- API version. (default: {"v1"}).
        """
        self.version = version
        self.target = target
        pitdata = Pit.get('editnet_apikey', {
            'require': {'edinet_apikey': 'edinet apikey'}
        })
        self.apikey = pitdata['edinet_apikey']

    @property
    def endpoint(self) -> str:
        return self.BASE_URL.format(self.version, self.target)
