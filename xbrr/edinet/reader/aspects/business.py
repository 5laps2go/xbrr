from xbrr.base.reader.base_parser import BaseParser
from xbrr.xbrl.reader.element_value import ElementValue


class Business(BaseParser):

    def __init__(self, reader):
        tags = {
            "policy_environment_issue_etc": "jpcrp_cor:BusinessPolicyBusinessEnvironmentIssuesToAddressEtcTextBlock",
            "risks": "jpcrp_cor:BusinessRisksTextBlock",
            "research_and_development": "jpcrp_cor:ResearchAndDevelopmentActivitiesTextBlock",
            "management_analysis": "jpcrp030000-asr_E05739-000:ManagementAnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock",
            "overview_of_result": "jpcrp_cor:OverviewOfBusinessResultsTextBlock",
            "overview_of_value_chain": "jpcrp_cor:OverviewOfProductionOrdersReceivedAndSalesTextBlock",
            "analysis_of_finance": "jpcrp_cor:AnalysisOfFinancialPositionOperatingResultsAndCashFlowsTextBlock"
        }
        super().__init__(reader, ElementValue, tags)
