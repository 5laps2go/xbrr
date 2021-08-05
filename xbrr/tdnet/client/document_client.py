import re
from pathlib import Path
import tempfile
from zipfile import ZipFile
import requests
from xbrr.edinet.models.error_response import ErrorResponse


class DocumentClient():
    """Client to get file."""

    BASE_URL = "https://www.release.tdnet.info/inbs/{}"

    def __init__(self):
        pass

    @property
    def endpoint(self):
        return self.BASE_URL

    def get(self, document_id: str,
            save_dir: str = "") -> str:
        """Get file of document_id and save it to save_dir/file_name.

        Arguments:
            document_id {str} -- Document id of EDINET.

        Keyword Arguments:
            save_dir {str} -- Directory to save file (default: {""}).

        Returns:
            str -- Path to saved file.
        """
        url = self.endpoint.format(document_id)

        r = requests.get(url, stream=True)

        if not r.ok:
            r.raise_for_status()
        else:
            _file_name = document_id
            chunk_size = 1024
            if save_dir:
                save_path = Path(save_dir).joinpath(_file_name)
            else:
                _file_name = Path(_file_name)
                tmpf = tempfile.NamedTemporaryFile(
                        prefix=_file_name.stem + "__",
                        suffix=_file_name.suffix,
                        delete=False)
                save_path = Path(tmpf.name)

            with save_path.open(mode="wb") as f:
                for chunk in r.iter_content(chunk_size):
                    f.write(chunk)

            return save_path

    def get_pdf(self, document_id: str,
                save_dir: str = "", file_name: str = "") -> str:
        """Get PDF file.

        Arguments:
            document_id {str} -- Document id of EDINET.

        Keyword Arguments:
            save_dir {str} -- Directory to save file (default: {""}).

        Returns:
            str -- Saved file path.
        """
        path = self.get(document_id+".pdf", save_dir)
        return path

    def get_xbrl(self, document_id: str,
                 save_dir: str = "",
                 expand_level: str = "dir"):
        """Get XBRL file.

        Arguments:
            document_id {str} -- Document id of TDNET.

        Keyword Arguments:
            save_dir {str} -- Directory to save file (default: {""}).
            expand_level {int} -- File expansion level
                                   ''    : Not expand, 
                                   'dir' : Expand zip,

        Returns:
            str -- Saved file path.
        """
        path = self.get(document_id+".zip", save_dir)

        if expand_level is None or not expand_level or\
           expand_level not in ("dir", "file"):
            return path

        assert expand_level == "dir"
        xbrl_dir = path.parent.joinpath(document_id)
        with ZipFile(path, "r") as zip:
            zip.extractall(path=xbrl_dir)
        path.unlink()
        return xbrl_dir
