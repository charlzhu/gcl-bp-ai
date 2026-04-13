from dataclasses import dataclass
from datetime import date

from backend.app.utils.time_utils import format_month, month_index


@dataclass(frozen=True)
class LogisticsRecord:
    record_id: str
    shipment_date: date
    company: str
    transport_mode: str
    business_type: str
    source_type: str
    warehouse: str
    destination: str
    shipment_watt: float
    shipment_trip_count: int
    total_fee: float
    extra_fee: float

    @property
    def year(self) -> int:
        return self.shipment_date.year

    @property
    def month(self) -> int:
        return self.shipment_date.month

    @property
    def month_key(self) -> str:
        return format_month(self.year, self.month)

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "shipment_date": self.shipment_date.isoformat(),
            "year": self.year,
            "month": self.month_key,
            "company": self.company,
            "transport_mode": self.transport_mode,
            "business_type": self.business_type,
            "source_type": self.source_type,
            "warehouse": self.warehouse,
            "destination": self.destination,
            "shipment_watt": round(self.shipment_watt, 2),
            "shipment_trip_count": self.shipment_trip_count,
            "total_fee": round(self.total_fee, 2),
            "extra_fee": round(self.extra_fee, 2),
        }


class InMemoryLogisticsQueryRepository:
    def __init__(self) -> None:
        self._records = self._build_demo_records()

    def list_records(
        self,
        *,
        start_month: str,
        end_month: str,
        companies: list[str] | None = None,
        transport_modes: list[str] | None = None,
        business_types: list[str] | None = None,
        source_type: str = "mixed",
        keyword: str | None = None,
    ) -> list[LogisticsRecord]:
        start_idx = month_index(start_month)
        end_idx = month_index(end_month)
        companies = companies or []
        transport_modes = transport_modes or []
        business_types = business_types or []
        keyword = keyword.strip().lower() if keyword else None

        result: list[LogisticsRecord] = []
        for record in self._records:
            current_idx = month_index(record.month_key)
            if current_idx < start_idx or current_idx > end_idx:
                continue
            if companies and record.company not in companies:
                continue
            if transport_modes and record.transport_mode not in transport_modes:
                continue
            if business_types and record.business_type not in business_types:
                continue
            if source_type != "mixed" and record.source_type != source_type:
                continue
            if keyword and keyword not in f"{record.company}{record.destination}{record.warehouse}".lower():
                continue
            result.append(record)

        return sorted(result, key=lambda item: (item.shipment_date, item.record_id))

    @staticmethod
    def _build_demo_records() -> list[LogisticsRecord]:
        return [
            LogisticsRecord(
                record_id="HIS-202501-001",
                shipment_date=date(2025, 1, 15),
                company="合肥基地",
                transport_mode="汽运",
                business_type="内贸",
                source_type="history",
                warehouse="合肥仓",
                destination="广州",
                shipment_watt=128.5,
                shipment_trip_count=3,
                total_fee=92000.0,
                extra_fee=3200.0,
            ),
            LogisticsRecord(
                record_id="HIS-202501-002",
                shipment_date=date(2025, 1, 20),
                company="阜宁基地",
                transport_mode="铁运",
                business_type="内贸",
                source_type="history",
                warehouse="阜宁仓",
                destination="天津",
                shipment_watt=143.2,
                shipment_trip_count=2,
                total_fee=84500.0,
                extra_fee=1800.0,
            ),
            LogisticsRecord(
                record_id="HIS-202502-001",
                shipment_date=date(2025, 2, 18),
                company="芜湖基地",
                transport_mode="海运",
                business_type="外贸",
                source_type="history",
                warehouse="芜湖港仓",
                destination="宁波",
                shipment_watt=152.4,
                shipment_trip_count=1,
                total_fee=110000.0,
                extra_fee=5500.0,
            ),
            LogisticsRecord(
                record_id="HIS-202503-001",
                shipment_date=date(2025, 3, 12),
                company="合肥基地",
                transport_mode="汽运",
                business_type="内贸",
                source_type="history",
                warehouse="合肥仓",
                destination="武汉",
                shipment_watt=136.7,
                shipment_trip_count=4,
                total_fee=99000.0,
                extra_fee=2600.0,
            ),
            LogisticsRecord(
                record_id="HIS-202601-001",
                shipment_date=date(2026, 1, 10),
                company="合肥基地",
                transport_mode="汽运",
                business_type="内贸",
                source_type="system_formal",
                warehouse="合肥仓",
                destination="广州",
                shipment_watt=168.3,
                shipment_trip_count=4,
                total_fee=108000.0,
                extra_fee=4200.0,
            ),
            LogisticsRecord(
                record_id="SYS-202601-002",
                shipment_date=date(2026, 1, 22),
                company="阜宁基地",
                transport_mode="铁运",
                business_type="外贸",
                source_type="system_formal",
                warehouse="阜宁仓",
                destination="连云港",
                shipment_watt=174.1,
                shipment_trip_count=3,
                total_fee=126000.0,
                extra_fee=3800.0,
            ),
            LogisticsRecord(
                record_id="SYS-202602-001",
                shipment_date=date(2026, 2, 8),
                company="芜湖基地",
                transport_mode="海运",
                business_type="外贸",
                source_type="system_formal",
                warehouse="芜湖港仓",
                destination="上海",
                shipment_watt=182.6,
                shipment_trip_count=2,
                total_fee=141500.0,
                extra_fee=6900.0,
            ),
            LogisticsRecord(
                record_id="SYS-202602-002",
                shipment_date=date(2026, 2, 19),
                company="合肥基地",
                transport_mode="汽运",
                business_type="内贸",
                source_type="system_formal",
                warehouse="合肥仓",
                destination="长沙",
                shipment_watt=165.4,
                shipment_trip_count=5,
                total_fee=117800.0,
                extra_fee=3500.0,
            ),
            LogisticsRecord(
                record_id="SYS-202603-001",
                shipment_date=date(2026, 3, 4),
                company="阜宁基地",
                transport_mode="铁运",
                business_type="内贸",
                source_type="system_formal",
                warehouse="阜宁仓",
                destination="重庆",
                shipment_watt=171.2,
                shipment_trip_count=3,
                total_fee=120500.0,
                extra_fee=2400.0,
            ),
            LogisticsRecord(
                record_id="SYS-202603-002",
                shipment_date=date(2026, 3, 26),
                company="芜湖基地",
                transport_mode="海运",
                business_type="外贸",
                source_type="system_formal",
                warehouse="芜湖港仓",
                destination="深圳",
                shipment_watt=188.9,
                shipment_trip_count=2,
                total_fee=149300.0,
                extra_fee=7100.0,
            ),
        ]
