from xbrr.base.reader.base_parser import BaseParser
from xbrr.edinet.reader.element_value import ElementValue


class Stock(BaseParser):

    def __init__(self, reader):
        tags = {
            "dividend_paid": "jpcrp_cor:DividendPaidPerShareSummaryOfBusinessResults",  # 一株配当
            "dividends_surplus": "jppfs_cor:DividendsFromSurplus",                      # 剰余金の配当
            "purchase_treasury_stock": "jppfs_cor:PurchaseOfTreasuryStock",             # 自社株買い
        }
        super().__init__(reader, ElementValue, tags)
