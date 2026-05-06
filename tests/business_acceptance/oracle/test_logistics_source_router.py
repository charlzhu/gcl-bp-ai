from __future__ import annotations

import sys
import unittest
from pathlib import Path


ORACLE_DIR = Path(__file__).resolve().parent
if str(ORACLE_DIR) not in sys.path:
    sys.path.insert(0, str(ORACLE_DIR))

from engine import NEED_CLARIFICATION, ORACLE_READY_CANDIDATE, LogisticsOracleEngine, convert_case_oracle_status
from source_router import extract_logistics_years, route_logistics_sources, route_logistics_year


class LogisticsSourceRouterTest(unittest.TestCase):
    """物流 Oracle Engine 年份路由回归测试。"""

    def test_historical_years_route_to_excel(self) -> None:
        """验证 2023-2025 年路由到 Excel。

        参数：无。
        返回值：无。
        """

        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual(route_logistics_year(year).source, "excel")

    def test_2026_and_future_years_route_to_mysql(self) -> None:
        """验证 2026 年及以后路由到 MySQL。

        参数：无。
        返回值：无。
        """

        for year in (2026, 2027):
            with self.subTest(year=year):
                self.assertEqual(route_logistics_year(year).source, "mysql")

    def test_extract_short_and_full_years_in_order(self) -> None:
        """验证两位年份和四位年份均可识别。

        参数：无。
        返回值：无。
        """

        self.assertEqual(extract_logistics_years("25年和2026年运量对比"), [2025, 2026])

    def test_question_source_routes_can_span_excel_and_mysql(self) -> None:
        """验证跨 2025/2026 的问题可形成混合来源路由。

        参数：无。
        返回值：无。
        """

        routes = route_logistics_sources("2025年和2026年物流运量对比")
        self.assertEqual([route.source for route in routes], ["excel", "mysql"])

    def test_ready_candidate_requires_year_and_metric(self) -> None:
        """验证物流 oracle_status 的候选转换规则。

        参数：无。
        返回值：无。
        """

        engine = LogisticsOracleEngine()
        ready = engine.prepare_case({"domain": "logistics", "question": "2025年各承运商运量分别是多少？"})
        missing_year = engine.prepare_case({"domain": "logistics", "question": "各承运商运量分别是多少？"})
        missing_metric = engine.prepare_case({"domain": "logistics", "question": "2026年物流情况怎么样？"})

        self.assertEqual(ready.oracle_status, ORACLE_READY_CANDIDATE)
        self.assertEqual(missing_year.oracle_status, NEED_CLARIFICATION)
        self.assertIn("year", missing_year.missing_slots)
        self.assertEqual(missing_metric.oracle_status, NEED_CLARIFICATION)
        self.assertIn("metric", missing_metric.missing_slots)

    def test_unsupported_import_status_is_preserved(self) -> None:
        """验证导入阶段的不支持边界不会被 Oracle Engine 改写。

        参数：无。
        返回值：无。
        """

        converted = convert_case_oracle_status(
            {
                "domain": "logistics",
                "question": "明天物流费用会不会上涨？",
                "oracle_status": "UNSUPPORTED",
            }
        )

        self.assertEqual(converted["oracle_status"], "UNSUPPORTED")
        self.assertFalse(converted["oracle_engine"]["handled"])


if __name__ == "__main__":
    unittest.main()
