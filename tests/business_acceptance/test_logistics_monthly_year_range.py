from __future__ import annotations

import unittest

from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.slot_extractor import LogisticsSlotExtractor


class LogisticsMonthlyYearRangeTest(unittest.TestCase):
    """物流历史跨年月度费用问法回归测试。"""

    def test_extract_years_supports_en_dash_range(self) -> None:
        """验证 2023–2025 这类 en dash 年份范围能完整展开。

        参数：无。
        返回值：无，断言失败时由 unittest 抛出异常。
        业务逻辑：Chrome/网页输入常出现 en dash，如果只识别普通连字符，会导致 planner 只取到末年。
        """

        extractor = LogisticsSlotExtractor()

        self.assertEqual(extractor.extract_years("2023–2025 年各月物流总费用是多少？"), [2023, 2024, 2025])

    def test_planner_keeps_multi_year_monthly_total_fee_scope(self) -> None:
        """验证跨年各月总费用不会退化成单一 2025 年。

        参数：无。
        返回值：无，断言失败时由 unittest 抛出异常。
        业务逻辑：2023–2025 年各月总费用应按 YYYY-MM 返回 36 个月，而不是只返回 2025 年 12 个月。
        """

        planner = LogisticsDataQaPlanner()
        questions = [
            "2023–2025 年各月物流总费用是多少？",
            "2023–2025年各月运费是多少？",
            "2023-2025年每个月运费是多少？",
        ]

        for question in questions:
            with self.subTest(question=question):
                plan = planner.build_plan(question)

                self.assertEqual(plan.query_key, "hist_monthly_total_fee_by_year")
                self.assertEqual(plan.filters.get("years"), [2023, 2024, 2025])
                self.assertNotEqual(plan.filters.get("year"), 2025)


if __name__ == "__main__":
    unittest.main()
