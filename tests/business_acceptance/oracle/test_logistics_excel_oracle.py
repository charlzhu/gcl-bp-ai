from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


ORACLE_DIR = Path(__file__).resolve().parent
if str(ORACLE_DIR) not in sys.path:
    sys.path.insert(0, str(ORACLE_DIR))

from engine import convert_case_oracle_status
from logistics_excel_calculator import CALCULATION_SUCCESS, NEED_ORACLE_IMPLEMENTATION
from logistics_excel_loader import LogisticsExcelSourceConfig, LogisticsExcelWorkbookLoader
from logistics_excel_mapping import LogisticsExcelFieldMapper, resolve_header_map


class LogisticsExcelOracleTest(unittest.TestCase):
    """物流 Excel Oracle P2.2 单元测试。"""

    def setUp(self) -> None:
        """准备脱敏 Excel fixture。

        参数：无。
        返回值：无。
        """

        self.temp_dir = tempfile.TemporaryDirectory()
        self.fixture_path = Path(self.temp_dir.name) / "logistics_2025_fixture.xlsx"
        self._write_fixture(self.fixture_path)
        self.config = LogisticsExcelSourceConfig(year_files={2025: self.fixture_path})

    def tearDown(self) -> None:
        """清理临时 fixture。

        参数：无。
        返回值：无。
        """

        self.temp_dir.cleanup()

    def test_excel_loader_reads_fixture_rows(self) -> None:
        """验证 Excel loader 可以读取 fixture。

        参数：无。
        返回值：无。
        """

        dataset = LogisticsExcelWorkbookLoader(self.config).load_year(2025)

        self.assertEqual(dataset.year, 2025)
        self.assertEqual(len(dataset.rows), 3)
        self.assertEqual(dataset.rows[0].biz_month, "2025-03")

    def test_field_mapping_resolves_raw_headers(self) -> None:
        """验证字段映射层把原始列名转换为标准字段。

        参数：无。
        返回值：无。
        """

        header_map = resolve_header_map(["发货日期", "日实际发运瓦数", "总费用（元）", "车辆数"])
        self.assertEqual(header_map["日实际发运瓦数"], "shipment_watt")
        self.assertEqual(header_map["总费用（元）"], "total_fee")
        self.assertEqual(header_map["车辆数"], "shipment_trip_count")

        mapped = LogisticsExcelFieldMapper().map_row(
            {
                "发货日期": date(2025, 3, 1),
                "日实际发运瓦数": "1200",
                "总费用（元）": "88.5",
                "车辆数": "2",
            },
            source_year=2025,
            source_file=self.fixture_path,
            row_no=2,
        )
        self.assertEqual(mapped.biz_month, "2025-03")
        self.assertEqual(str(mapped.shipment_watt), "1200")
        self.assertEqual(str(mapped.total_fee), "88.5")
        self.assertEqual(str(mapped.shipment_trip_count), "2")

    def test_monthly_shipment_watt_calculation(self) -> None:
        """验证月度运量按瓦数口径求和。

        参数：无。
        返回值：无。
        """

        converted = convert_case_oracle_status(
            {
                "case_id": "BA-EXCEL-TEST-001",
                "question": "2025年3月物流运量是多少？",
                "domain": "logistics",
                "oracle_status": "NEED_ORACLE",
            },
            excel_source_config=self.config,
        )

        expected = converted["expected_result"]
        self.assertEqual(expected["calculation_status"], CALCULATION_SUCCESS)
        self.assertEqual(expected["metric"], "shipment_watt")
        self.assertEqual(expected["year"], 2025)
        self.assertEqual(expected["month"], 3)
        self.assertEqual(expected["value"], 3500.0)
        self.assertEqual(expected["unit"], "W")

    def test_monthly_freight_cost_calculation(self) -> None:
        """验证月度运费求和。

        参数：无。
        返回值：无。
        """

        converted = convert_case_oracle_status(
            {
                "case_id": "BA-EXCEL-TEST-002",
                "question": "2025年3月总运费是多少？",
                "domain": "logistics",
                "oracle_status": "NEED_ORACLE",
            },
            excel_source_config=self.config,
        )

        expected = converted["expected_result"]
        self.assertEqual(expected["calculation_status"], CALCULATION_SUCCESS)
        self.assertEqual(expected["metric"], "freight_cost")
        self.assertEqual(expected["value"], 421.25)
        self.assertEqual(expected["unit"], "元")

    def test_unsupported_metric_returns_need_oracle_implementation(self) -> None:
        """验证未实现指标不会猜测答案。

        参数：无。
        返回值：无。
        """

        converted = convert_case_oracle_status(
            {
                "case_id": "BA-EXCEL-TEST-003",
                "question": "2025年3月平均运价是多少？",
                "domain": "logistics",
                "oracle_status": "NEED_ORACLE",
            },
            excel_source_config=self.config,
        )

        expected = converted["expected_result"]
        self.assertEqual(expected["metric"], "unit_price")
        self.assertEqual(expected["calculation_status"], NEED_ORACLE_IMPLEMENTATION)
        self.assertIsNone(expected["value"])

    def _write_fixture(self, path: Path) -> None:
        """写入测试 Excel fixture。

        参数：
            path：fixture 文件路径。
        返回值：无。
        """

        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "物流台账"
        worksheet.append(["发货日期", "日实际发运瓦数", "总费用(元)", "车辆数"])
        worksheet.append([date(2025, 3, 5), 1000, 120.50, 1])
        worksheet.append([date(2025, 3, 20), 2500, 300.75, 2])
        worksheet.append([date(2025, 4, 1), 800, 88.00, 1])
        workbook.save(path)


if __name__ == "__main__":
    unittest.main()
