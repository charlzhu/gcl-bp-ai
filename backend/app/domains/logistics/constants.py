AVAILABLE_METRICS = (
    "shipment_watt",
    "shipment_trip_count",
    "total_fee",
    "extra_fee",
)
AVAILABLE_GROUP_FIELDS = (
    "year",
    "month",
    "company",
    "transport_mode",
    "business_type",
    "source_type",
)
AVAILABLE_SOURCE_TYPES = ("history", "system_formal", "mixed")
SUPPORTED_UPLOAD_SUFFIXES = {".xlsx", ".xls", ".csv"}
DEFAULT_METRICS = ("shipment_watt",)
DEFAULT_GROUP_FIELDS = ("month",)
METRIC_LABELS = {
    "shipment_watt": "运量(瓦数口径)",
    "shipment_trip_count": "发运车次",
    "total_fee": "总费用",
    "extra_fee": "附加费",
}
TRANSPORT_MODES = ("汽运", "铁路", "水运")
BUSINESS_TYPES = ("内贸", "外贸")
COMPANIES = ("合肥基地", "阜宁基地", "芜湖基地")
REGIONS = ("华东", "华北", "华南", "华中", "西北", "西南", "东北")
