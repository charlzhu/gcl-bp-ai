import re

from backend.app.domains.logistics.constants import BUSINESS_TYPES, COMPANIES, METRIC_LABELS, TRANSPORT_MODES

INTENT_COMPARE_KEYWORDS = ("同比", "环比", "对比", "比较")
INTENT_DETAIL_KEYWORDS = ("明细", "详情", "订单", "列表")
METRIC_KEYWORDS = {
    "shipment_watt": ("运量", "发货量", "瓦数", "w"),
    "shipment_trip_count": ("车次", "趟次", "运输次数"),
    "total_fee": ("费用", "运费", "总费用"),
    "extra_fee": ("附加费",),
}
COMPARE_MODE_KEYWORDS = {
    "yoy": ("同比",),
    "mom": ("环比",),
}


def infer_intent(question: str) -> str:
    if any(keyword in question for keyword in INTENT_DETAIL_KEYWORDS):
        return "detail"
    if any(keyword in question for keyword in INTENT_COMPARE_KEYWORDS):
        return "compare"
    return "metrics"


def infer_metric(question: str) -> str:
    lowered = question.lower()
    for metric, keywords in METRIC_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return metric
    return "shipment_watt"


def infer_compare_mode(question: str) -> str | None:
    for mode, keywords in COMPARE_MODE_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return mode
    return None


def extract_companies(question: str) -> list[str]:
    return [company for company in COMPANIES if company in question]


def extract_transport_modes(question: str) -> list[str]:
    return [mode for mode in TRANSPORT_MODES if mode in question]


def extract_business_types(question: str) -> list[str]:
    return [business_type for business_type in BUSINESS_TYPES if business_type in question]


def metric_label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def extract_period_tokens(question: str) -> list[tuple[int, int | None]]:
    month_tokens = [
        (int(match.group("year")), int(match.group("month")))
        for match in re.finditer(r"(?P<year>\d{4})年(?P<month>\d{1,2})月", question)
    ]
    if month_tokens:
        return month_tokens

    year_tokens = [
        (int(match.group("year")), None)
        for match in re.finditer(r"(?P<year>\d{4})年", question)
    ]
    return year_tokens
