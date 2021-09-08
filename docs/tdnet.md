# TDNET reader

Following aspects are supported. 

0. 文書情報: `Forecast`
    1. 文書名: `document_name`
    2. 提出日: `filing_date`
    3. 上場会社名: `company_name`
    4. コード番号: `security_code`
    5. 予想修正報告日: `forecast_correction_date`
1. 経営成績
2. 財政状態
3. 配当の状況 `Forecast`
    1. 年間配当金 `fc_dividends`
4. 業績予想 `Forecast`
    1. 通期: `fc`
        * 売上高 営業利益 経常利益 当期純利益 １株当たり当期純利益所有者別状況

## References

* [決算短信作成要領・四半期決算短信作成要領](https://www.jpx.co.jp/equities/listed-co/format/summary/index.html)