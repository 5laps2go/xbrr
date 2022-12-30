import re
from datetime import datetime
from typing import Dict, Union

import requests
import urllib3
from bs4 import BeautifulSoup

from xbrr.tdnet.models import Documents


class BaseDocumentListClient():
    """Base client to handle tdnet pages scraping."""

    TDNET_INFO_PAGE = "https://www.release.tdnet.info/inbs/I_list_001_{}.html"
    TDNET_INFO_EACH_PAGE = "https://www.release.tdnet.info/inbs/{}"

    def __init__(self):
        self.session = self.open_session()

    def _get(self, date: Union[str, datetime]) -> Dict:
        """Get scraped document list.

        Arguments:
            date {(str, datetime)} -- Request date.

        Raises:
            Exception: Date format exception.

        Returns:
            dict -- TDNET Response (JSON).
        """
        _date:datetime
        try:
            _date = date if isinstance(date, datetime) else datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise Exception("Date format should be yyyy-mm-dd.")

        url = self.TDNET_INFO_PAGE.format(_date.strftime("%Y%m%d"))
        tdnet_date_page = self.session.get(url)
        if tdnet_date_page.status_code != requests.codes.ok:
            return {"metadata": {"resultset":{"count":0}}}

        soup = BeautifulSoup(tdnet_date_page.content, "html.parser")
        items_l = self.fetch_tdnet_info_per_page(_date, soup)

        others_el = soup.select("#pager-box-top > div.pager-M")
        other_page_urls = [re.findall(r'\'(.*)\'',x["onclick"])[0] for x in others_el]  # type: ignore
        for other_page in other_page_urls:
            url = self.TDNET_INFO_EACH_PAGE.format(other_page)
            tdnet_other_page = self.session.get(url)
            if tdnet_date_page.status_code != requests.codes.ok:
                return {"metadata": {"resultset":{"count":0}}}
            soup = BeautifulSoup(tdnet_other_page.content, "html.parser")
            items_l.extend(self.fetch_tdnet_info_per_page(_date, soup))
        return {"metadata": {"resultset":{"count":len(items_l)}},
                "results": items_l}

    def fetch_tdnet_info_per_page(self, date: datetime, soup: BeautifulSoup):
        items_l = []
        list_el = soup.select('#main-list-table > tr')
        for item_el in list_el:
            entry = {}
            entry['pubdate'] = '{} {}:00'.format(date.strftime("%Y-%m-%d"), item_el.select_one("td.kjTime").text)
            entry['company_code'] = item_el.select_one("td.kjCode").text
            entry['company_name'] = item_el.select_one("td.kjName").text
            entry['title'] = item_el.select_one("td.kjTitle").text.strip()
            doc_el = item_el.select_one("td.kjTitle a")
            doc_el = item_el.select_one("td.kjTitle a")
            entry['document_url'] = None if doc_el is None \
                else 'https://www.release.tdnet.info/inbs/{}'.format(doc_el['href'])
            xbrl_el = item_el.select_one("td.kjXbrl a")
            entry['url_xbrl'] =  None if xbrl_el is None \
                else 'https://www.release.tdnet.info/inbs/{}'.format(xbrl_el['href'])
            entry['markets_string'] = item_el.select_one("td.kjPlace").text
            entry['update_history'] = item_el.select_one("td.kjHistroy").text
            tdnet = {'Tdnet': entry}
            items_l.append(tdnet)
        return items_l

    def open_session(self):
        session = requests.session()
        retries = urllib3.util.Retry(total=3,  # リトライ回数
                        backoff_factor=1,  # sleep時間
                        status_forcelist=[500, 502, 503, 504])  # timeout以外でリトライするステータスコード
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retries))  # type: ignore
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=retries))  # type: ignore
        return session

class DocumentListClient(BaseDocumentListClient):
    """Client to get document list."""

    def get(self, date: Union[str, datetime]) -> Documents:
        """Get metadeta response.

        Arguments:
            date {(str, datetime)} -- Request date.

        Returns:
            Documents -- Document list and its metadata.
        """
        body = self._get(date)
        instance = Documents.create(body)
        return instance
