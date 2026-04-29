from __future__ import annotations

import argparse
import re
import sys
import zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.db.session import SessionLocal
from trial_sample_eval_common import (
    DEFAULT_BOM_ZIP,
    DEFAULT_HIST_ZIP,
    DEFAULT_SYS_ZIP,
    DOCS_DIR,
    EXPECTED_PATH,
    EXPECTED_REPORT_PATH,
    LEDGER_PATH,
    PROJECT_ROOT,
    extract_months,
    extract_top_n,
    extract_years,
    now_iso,
    read_json,
    write_json,
    write_markdown,
)


PROJECT_TOTAL_TRUCKS_SQL = """
    CASE
        WHEN st.project_name IS NULL OR st.project_name = '' THEN NULL
        WHEN SUBSTRING_INDEX(SUBSTRING_INDEX(st.project_name, '-', 3), '-', -1) REGEXP '^[0-9]+(\\.[0-9]+)?$'
            THEN CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(st.project_name, '-', 3), '-', -1) AS DECIMAL(18,2))
        ELSE NULL
    END
"""

HIST_DIMENSIONS = {
    "省份": ("province", "省份"),
    "省": ("province", "省份"),
    "城市": ("city", "城市"),
    "区域": ("region_name", "区域"),
    "始发": ("origin_place", "始发地"),
    "客户": ("customer_name", "客户"),
    "承运商": ("logistics_company_name", "承运商"),
    "物流公司": ("logistics_company_name", "承运商"),
    "物流供应商": ("logistics_company_name", "承运商"),
    "各家物流": ("logistics_company_name", "承运商"),
    "各物流": ("logistics_company_name", "承运商"),
    "车型": ("required_vehicle_type", "车型"),
    "运输方式": ("transport_mode", "运输方式"),
    "产品规格": ("product_spec", "产品规格"),
    "规格": ("product_spec", "产品规格"),
    "功率": ("product_power", "功率"),
}

METRIC_KEYWORDS = {
    # 额外费用必须优先于“费用/运输费用”泛化词，否则会被误核算为总运费。
    "extra_fee": ["额外费用", "异常费用"],
    "unit_fee_per_watt": ["平均单瓦价", "单瓦价"],
    "avg_fee_per_watt": ["平均元/瓦", "元/瓦", "单瓦运输成本", "平均单瓦运输成本", "单瓦成本", "单瓦费用"],
    "avg_fee_per_trip": ["平均单车运费", "平均单车运输费用", "平均单价/车", "单价/车", "平均每车运费", "单车均价"],
    "avg_fee": ["平均运费", "平均运输费用", "平均费用", "均价"],
    "record_count": ["发运记录数", "记录数"],
    "actual_qty": ["发运件数", "发货件数", "总件数", "件数"],
    "total_fee": ["运费", "费用", "总费用", "运输费用"],
    "actual_watt": ["发运量", "运量", "发货量", "mw", "MW", "瓦"],
    "shipment_trip_count": ["车次", "车辆", "车数", "多少车", "发出了多少车", "发运多少车"],
}

PROVINCES = [
    "江苏",
    "浙江",
    "安徽",
    "山东",
    "上海",
    "北京",
    "天津",
    "河北",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "广西",
    "福建",
    "江西",
    "四川",
    "重庆",
    "陕西",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "内蒙古",
    "新疆",
    "宁夏",
    "云南",
    "贵州",
    "海南",
    "甘肃",
    "青海",
    "西藏",
]

REGIONS = ["华东", "华中", "华南", "华北", "西北", "西南", "东北"]

MATERIAL_ALIASES = {
    "glass": ["玻璃", "玻璃规格", "玻璃描述"],
    "gap_film": ["间隙贴膜", "间隙膜"],
    "interconnect_bar": ["焊带", "互联条"],
    "busbar": ["汇流条"],
    "junction_box": ["接线盒", "线盒"],
    "poe_film": ["POE胶膜", "POE 胶膜", "POE"],
    "eva_film": ["EVA胶膜", "EVA 胶膜", "EVA"],
    "cell": ["电池片", "电池片方案"],
    "frame": ["边框"],
}


def _decimal_to_float(value: Any) -> float | None:
    """把数据库 Decimal 转成可写入 JSON 的浮点数。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _zip_audit(path: Path) -> dict[str, Any]:
    """读取 zip 基础信息，只做源文件存在性和文件范围核验。"""
    if not path.exists():
        return {"path": str(path), "exists": False, "error": "file_not_found"}
    try:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if not name.startswith("__MACOSX/") and not name.endswith("/")]
            excels = [name for name in names if name.lower().endswith((".xls", ".xlsx"))]
            return {
                "path": str(path),
                "exists": True,
                "file_count": len(names),
                "excel_count": len(excels),
                "sample_files": names[:20],
            }
    except Exception as exc:  # noqa: BLE001
        return {"path": str(path), "exists": True, "error": str(exc)}


def _db_audit() -> dict[str, Any]:
    """核验 logistics_ai 中间库表行数和日期范围。"""
    tables = [
        "dwd_logistics_hist_shipment_detail",
        "dwd_logistics_ship_task",
        "dwd_logistics_ship_product",
        "dwd_logistics_assign_task",
        "dwd_logistics_assign_detail",
    ]
    audit: dict[str, Any] = {"available": False, "tables": {}}
    db = SessionLocal()
    try:
        for table in tables:
            row = db.execute(
                text(
                    f"""
                    SELECT COUNT(*) AS row_count
                    FROM {table}
                    """
                )
            ).mappings().first()
            audit["tables"][table] = {"row_count": int(row["row_count"] or 0)}
        hist_range = db.execute(
            text(
                """
                SELECT MIN(biz_date) AS min_date, MAX(biz_date) AS max_date, COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                """
            )
        ).mappings().first()
        sys_range = db.execute(
            text(
                """
                SELECT MIN(COALESCE(pickup_date, biz_date)) AS min_date,
                       MAX(COALESCE(pickup_date, biz_date)) AS max_date,
                       COUNT(*) AS row_count
                FROM dwd_logistics_ship_task
                """
            )
        ).mappings().first()
        audit["ranges"] = {
            "history": dict(hist_range or {}),
            "system_2026": dict(sys_range or {}),
        }
        audit["available"] = True
    except Exception as exc:  # noqa: BLE001
        audit["error"] = str(exc)
    finally:
        db.close()
    return audit


def _metric_for_question(question: str) -> tuple[str, str, str]:
    """识别物流指标和单位。"""
    lowered = question.lower()
    for metric, keywords in METRIC_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            if metric == "actual_watt":
                return metric, "MW", "发运量"
            if metric == "actual_qty":
                return metric, "件", "总发运件数"
            if metric == "avg_fee_per_watt":
                return metric, "元/瓦", "平均元/瓦"
            if metric == "unit_fee_per_watt":
                return metric, "元/瓦", "平均单瓦价"
            if metric == "avg_fee_per_trip":
                return metric, "元/车", "平均单价/车"
            if metric == "avg_fee":
                return metric, "元", "平均运费"
            if metric == "record_count":
                return metric, "条", "发运记录数"
            if metric == "shipment_trip_count":
                return metric, "车次", "车次"
            if metric == "extra_fee":
                return metric, "元", "额外费用"
            return metric, "元", "总运费"
    return "total_fee", "元", "总运费"


def _dimensions_for_question(question: str) -> list[tuple[str, str]]:
    """识别物流分组维度。"""
    dims: list[tuple[str, str]] = []
    if any(word in question for word in ["每月", "每个月", "月度", "各月", "按月"]):
        dims.append(("biz_month", "月份"))
    for keyword, dimension in HIST_DIMENSIONS.items():
        if keyword in question and dimension not in dims:
            dims.append(dimension)
    return dims


def _is_hist_origin_vehicle_breakdown_question(question: str) -> bool:
    """识别历史始发地 + 车型维度的多指标汇总题。

    参数：
        question: 原始样例题文本。
    返回值：
        属于该题型时返回 True，否则返回 False。
    """

    compact = re.sub(r"\s+", "", question)
    if "不同车型" not in compact or "始发" not in compact:
        return False
    metric_hits = sum(
        1
        for keyword_group in (
            ("发运车次", "车次", "车数"),
            ("总费用", "总运费", "运输费用"),
            ("平均单车费用", "平均单车运费", "平均单价/车"),
        )
        if any(keyword in compact for keyword in keyword_group)
    )
    return metric_hits >= 2


def _province_filter(question: str) -> str | None:
    """从题目中提取省份过滤。"""
    for province in PROVINCES:
        if province in question:
            return f"{province}省" if not province.endswith(("省", "市", "区")) else province
    return None


def _region_filter(question: str) -> str | None:
    """从题目中提取明确区域过滤条件。"""
    for region in REGIONS:
        if region in question:
            return region
    return None


def _origin_place_filter(question: str) -> str | None:
    """从题目中提取常见始发地过滤条件。"""
    # “合肥城市发运”在样例题里表达的是目的城市维度，不是始发地过滤；
    # 标准答案核算层必须和正式查询链路保持同一业务口径，避免双重过滤。
    if "城市发运" in question:
        return None
    for origin in ("合肥", "阜宁"):
        if origin in question:
            return origin
    return None


def _carrier_filter(question: str) -> str | None:
    """从题目中提取常见承运商过滤条件。"""
    if "晶茂" in question:
        return "晶茂"
    if "英赋嘉" in question:
        return "英赋嘉"
    return None


def _customer_filter(question: str) -> str | None:
    """从题目中提取样例题中可稳定识别的客户前缀。"""
    import re

    compact = re.sub(r"\s+", "", question)
    patterns = [
        r"客户[:：]?(.+?)(?:总运输费用|运输费用|总运费|运费|总发运量|发运量|总运量|运量|已发出总运量)",
        r"客户(.+?)(?:的总发运量|发运量|总运量|运量|发货的项目地)",
    ]
    for pattern in patterns:
        matched = re.search(pattern, compact)
        if not matched:
            continue
        customer = matched.group(1)
        customer = re.sub(r"\d{2,4}年", "", customer)
        customer = customer.replace("全年", "").replace("已发出", "").replace("总计", "")
        customer = customer.replace("发货的", "").replace("发货", "").replace("项目", "")
        customer = re.sub(r"客户$", "", customer).strip(" ：:，,。？！?")
        if customer:
            return customer
    if "华润新能源" in question and "皮山" in question:
        return "华润新能源(皮山)有限公司"
    return None


def _product_spec_filter(question: str) -> str | None:
    """从题目中提取明确产品规格过滤条件。"""
    import re

    matched = re.search(r"规格(?:为|是)?\s*([A-Za-z0-9_/\-.]+)", question)
    if matched:
        return matched.group(1).rstrip("的,，。?？")
    matched = re.search(r"(GCL-[A-Za-z0-9_/\-.]+)", question)
    if matched:
        return matched.group(1).rstrip("的,，。?？")
    return None


def _city_filter(question: str) -> str | None:
    """从题目中提取明确城市过滤条件。

    说明：
        样例题常用“苏州城市发运”“合肥城市发运”表达目的城市过滤；
        这里只做通用中文城市片段识别，不绑定任何单题答案。
    """
    import re

    matched = re.search(r"([\u4e00-\u9fa5]{2,8})城市发运", question)
    if matched:
        return matched.group(1)
    matched = re.search(r"城市[为是]?([\u4e00-\u9fa5]{2,8})", question)
    if matched:
        return matched.group(1)
    compact = re.sub(r"\s+", "", question)
    matched = re.search(r"(?:发往|发)([\u4e00-\u9fa5]{2,10})(?:的)?(?:平均|总|累计|全年|每车|运费|运输费用|发运量)", compact)
    if matched:
        city = re.sub(r"(的)?(平均|总|累计|全年|每车).*$", "", matched.group(1)).replace("市", "").replace("省", "").strip()
        if city and city not in PROVINCES and city not in REGIONS:
            return city
    return None


def _transport_mode_filter(question: str) -> str | None:
    """提取明确运输方式过滤条件。"""
    aliases = {
        "汽运": "公路",
        "公路": "公路",
        "铁路": "铁路",
        "铁运": "铁路",
        "水路": "水路",
        "多式联运": "多式联运",
    }
    for alias, normalized in aliases.items():
        if alias in question:
            return normalized
    return None


def _vehicle_type_filter(question: str) -> str | None:
    """提取线路运价题中的车型口径。"""
    lowered = question.lower()
    if "17.5" in lowered or "17米五" in question or "17米5" in question:
        return "17.5"
    if "13m" in lowered or "13米" in question:
        return "13"
    if "9.6" in lowered or "9米6" in question:
        return "9.6"
    return None


def _destination_city_filter(question: str) -> str | None:
    """提取线路运价题中的目的城市。"""
    import re

    compact = re.sub(r"\s+", "", question)
    matched = re.search(r"(?:合肥|阜宁)发([\u4e00-\u9fa5]{2,10})(?:13m|13米|17\.5|17米五|17米5|运费|运输费用|运价|报价)", compact)
    if matched:
        city = matched.group(1).replace("市", "").replace("省", "").strip()
        city = re.sub(r"(的)?(平均|总|累计|全年).*$", "", city).strip()
        if city and city not in PROVINCES and city not in REGIONS:
            return city
    return None


def _sys_customer_filter(question: str) -> str | None:
    """提取 2026 系统侧项目/客户名称过滤。"""
    import re

    matched = re.search(r"客户[:：]?(.+?)(?:总运费|运输费用|运费|总费用|多少)", question)
    if matched:
        return matched.group(1).strip(" ：:，,。？！?")
    return None


def _sys_company_filter(question: str) -> str | None:
    """提取 2026 系统侧承运商过滤。"""
    if "晶茂" in question:
        return "晶茂"
    if "英赋嘉" in question:
        return "英赋嘉"
    return None


def _sys_procurement_type_filter(question: str) -> str | None:
    """提取 2026 系统侧采购方式过滤。"""
    if "询比价" in question:
        return "询比价"
    if "招标" in question:
        return "招标"
    return None


def _sys_base_code_filter(question: str) -> str | None:
    """提取 2026 系统侧基地编码过滤。"""
    if "阜宁基地" in question:
        return "2"
    if "合肥基地" in question:
        return "1"
    return None


def _should_default_to_history_years(question: str) -> bool:
    """判断缺少年份时是否可按历史台账默认范围核算。

    说明：
        样例题里大量历史物流问题省略了“2023-2025”，前端正式链路按历史台账累计口径回答；
        预测、未来、条件咨询类问题不能套用默认年份。
    """
    if "历史" in question:
        return True
    blocked_words = ["下个月", "预测", "未来", "需要哪些条件", "需要什么条件", "能否", "是否"]
    if any(word in question for word in blocked_words):
        return False
    if "功率产品" in question and any(word in question for word in ("按物流公司", "按承运商")):
        # 功率产品按承运商拆分同时涉及承运量、费用、元/瓦等多指标；
        # 当前正式前端要求用户先确认时间范围，标准答案层不能默认套用全历史范围。
        return False
    history_words = ["历史", "区域", "省", "城市", "运输方式", "规格", "发运", "运费", "元/瓦", "承运商", "客户"]
    return any(word in question for word in history_words)


def _is_complex_report_question(question: str) -> bool:
    """识别当前应作为 B 类追问处理的复杂报表题。

    参数：
        question: 样例题文本。

    返回：
        命中宽表、透视表、同比变化、多指标经营汇总表时返回 True。

    说明：
        标准答案层不能把前端当前不支持的报表模板能力强行标为 A；
        这类题需要先确认模板、维度和指标口径。
    """

    compact = re.sub(r"\s+", "", question)
    complex_keywords = (
        "宽表",
        "透视表",
        "经营总表",
        "经营汇总表",
        "区域经营表",
        "区域经营分析表",
        "结构表",
        "季度经营",
        "月报表",
        "同一张明细汇总表",
        "热力表",
        "交叉表",
        "矩阵表",
        "二维交叉表",
        "同比变化额",
        "同比变化率",
        "变化额和变化率",
        "并补充对应",
        "前20条记录",
        "发货日期",
        "按年度拆分",
        "年度拆分",
        "发运量占比",
        "运量占比",
        "费用占比",
        "前十条线路",
        "年度对比表",
        "每年的发运量",
        "平均单价/车和平均元/瓦",
        "物流公司数量",
        "承运商数量",
        "使用物流公司最多",
        "使用承运商最多",
        "同一询比价编号",
        "多个物流公司",
        "多个承运商",
        "Top10和Bottom10",
        "目的省份和车型组合",
    )
    if any(keyword in compact for keyword in complex_keywords):
        return True
    if (
        any(keyword in compact for keyword in ("平均单价/车", "平均单车", "平均元/瓦"))
        and any(keyword in compact for keyword in ("发运量", "运量", "发运瓦数"))
        and any(keyword in compact for keyword in ("总费用", "总运费", "运输费用"))
    ):
        return True
    if (
        any(keyword in compact for keyword in ("发运量", "运量", "发运瓦数"))
        and any(keyword in compact for keyword in ("总费用", "总运费", "运输费用"))
        and any(keyword in compact for keyword in ("车次", "车辆数", "车数"))
    ):
        return True
    if (
        any(keyword in compact for keyword in ("车次或车辆数", "车次/车辆数", "车次", "车辆数", "车数"))
        and any(keyword in compact for keyword in ("平均单车费用", "平均单车运费", "平均单价/车", "单车费用"))
        and any(keyword in compact for keyword in ("跨年对比", "每年", "年度对比", "每年的"))
    ):
        # 车辆数是否去重、平均单车费用分母是车次还是车辆，属于业务口径；
        # 标准答案不能用单一总费用结果替代跨年车辆效率表。
        return True
    if (
        any(keyword in compact for keyword in ("额外费用", "异常费", "异常费用"))
        and any(keyword in compact for keyword in ("涉及记录数", "记录数", "涉及客户数", "平均金额", "费用率", "按月份", "按物流公司", "按承运商", "按区域"))
    ):
        # “额外费用/异常费”在历史台账中存在可疑字段，但正式口径需要明确费用类型、
        # 审核状态、费用率分母等业务定义，不能直接按某一字段硬算为 A。
        return True
    if (
        "备注中包含" in compact
        and any(keyword in compact for keyword in ("倒运", "中转", "换车", "压车", "放空"))
        and any(keyword in compact for keyword in ("费用金额", "金额", "费用"))
    ):
        # 备注关键词只能说明业务场景，费用字段归属和异常认定仍需确认。
        return True
    if (
        "备注中包含" in compact
        and any(keyword in compact for keyword in ("历史发运记录数量", "发运记录数量", "记录数量", "总费用", "涉及区域", "按年份拆分", "前50条明细", "明细"))
    ):
        # 备注关键词不是标准结构化维度，涉及记录、费用和明细时需要先确认关键词字段、
        # 匹配方式和输出明细口径，不能按其他维度误算。
        return True
    if "日实际发运件数" in compact and "日计划发运件数" in compact:
        # 计划/实际件数差异需要先确认计划字段来源、日粒度和超发/缺口计算口径。
        return True
    if "同一车号" in compact and "同一天" in compact and any(keyword in compact for keyword in ("多个客户", "客户数", "线路数")):
        # 车号、日期、客户和线路的异常组合检查属于明细稽核，不是当前聚合查询能力。
        return True
    if (
        any(keyword in compact for keyword in ("项目名称", "每个项目", "项目“", "项目\""))
        and any(keyword in compact for keyword in ("任务数", "产品数量", "涉及省份", "涉及物流公司", "涉及承运商", "收货省市", "未签收", "待派车", "任务明细", "跨省发货"))
    ):
        # 项目名称尚未作为稳定统计维度接入，任务明细和跨省项目分析需要先固化项目口径。
        return True
    if "发货类型" in compact and any(keyword in compact for keyword in ("正常发货", "辅料送样", "客户项目数", "产品数量", "任务数")):
        # 发货类型、客户项目数和产品数量涉及系统侧多表口径，当前不能直接按费用查询替代。
        return True
    if (
        any(keyword in compact for keyword in ("项目数量", "提货单位", "采购类型"))
        and any(keyword in compact for keyword in ("收货省份数量", "收货城市数量", "主要物流公司", "主要承运商", "主要目的省份", "按月份", "收货省份的分布"))
    ):
        # 项目数量、提货单位和采购类型分布依赖系统侧多表定义，当前不能用总费用分组代替。
        return True
    if (
        any(keyword in compact for keyword in ("发货产品", "产品功率", "功率为"))
        and any(keyword in compact for keyword in ("产品名称", "规格", "产品数量", "任务数", "涉及项目", "收货省份分布", "交叉表"))
    ):
        # 产品名称、规格、功率和产品数量属于系统产品明细口径；
        # 当前标准答案不能用物流费用/省份分组替代产品数量统计。
        return True
    if "仓库绑定" in compact and any(keyword in compact for keyword in ("人员数量", "未绑定人员", "人员最少")):
        # 仓库人员绑定不属于当前物流/BOM 问答稳定业务域，需要先确认业务域和数据源。
        return True
    return "汇总成" in compact and any(keyword in compact for keyword in ("年度", "季度", "三层维度"))


def _is_2026_special_scope_mw_without_months(question: str, years: list[int], months: list[int]) -> bool:
    """识别 2026 特殊业务范围但缺少月份的发运量题。

    参数：
        question: 样例题文本。
        years: 已解析年份。
        months: 已解析月份。

    返回：
        用户问经营计划、辅料送样、刘娟用车等范围的发运量，但未给月份时返回 True。
    """

    compact = re.sub(r"\s+", "", question)
    return (
        max(years or [0]) >= 2026
        and not months
        and any(keyword in compact for keyword in ("经营计划", "辅料送样", "刘娟"))
        and any(keyword in compact for keyword in ("发运量", "总发运量", "总运量", "运量"))
    )


def _version_rank(version: str | None) -> tuple[int, str]:
    """把 BOM 版本号转换为可排序键。

    参数：
        version: 版本号，例如 A0、A1、A2。
    返回：
        排序键；数字越大代表越新的版本。
    """

    import re

    value = (version or "").strip().upper()
    matched = re.match(r"([A-Z]+)(\d+)", value)
    if matched:
        prefix, number = matched.groups()
        prefix_score = sum((ord(char) - 64) for char in prefix)
        return prefix_score, number.zfill(6)
    return 0, value


def _clarification_expected(reason: str, missing_slots: list[str] | None = None) -> dict[str, Any]:
    """构造需要业务补充口径的标准答案。

    参数：
        reason: 为什么不能直接核算。
        missing_slots: 需要业务补充的条件。
    返回：
        B 类标准答案结构。
    """

    return {
        "expected_status": "needs_clarification",
        "answer_type": "clarification",
        "reason": reason,
        "missing_slots": missing_slots or ["业务口径"],
    }


def _unsupported_expected(reason: str) -> dict[str, Any]:
    """构造当前数据或能力无法支撑的标准答案。"""

    return {
        "expected_status": "unsupported",
        "answer_type": "unsupported",
        "reason": reason,
    }


def _build_hist_route_pricing_expected(db, question: str, years: list[int]) -> dict[str, Any] | None:
    """独立核算历史线路运价类标准答案。

    参数：
        db: SQLAlchemy 会话。
        question: 样例题文本。
        years: 题目中明确出现的年份列表。

    返回：
        可核算时返回标准答案字典；不属于线路运价题时返回 None。
    """

    vehicle_type = _vehicle_type_filter(question)
    origin_place = _origin_place_filter(question)
    province = _province_filter(question)
    city = None if province else _destination_city_filter(question)
    if not vehicle_type or not origin_place or not (province or city):
        return None
    if not any(word in question for word in ("运价", "报价", "平均运费", "运费", "运输费用")):
        return None
    route_years = years or [2023, 2024, 2025]
    if any(year not in {2023, 2024, 2025} for year in route_years):
        return None

    filters = ["required_vehicle_type LIKE :vehicle_type"]
    params: dict[str, Any] = {"vehicle_type": f"%{vehicle_type}%"}
    year_placeholders = ", ".join(f":year_{idx}" for idx, _year in enumerate(route_years))
    filters.append(f"biz_year IN ({year_placeholders})")
    for idx, year in enumerate(route_years):
        params[f"year_{idx}"] = year
    filters.append("origin_place = :origin_place")
    params["origin_place"] = origin_place
    if city:
        filters.append("city = :city")
        params["city"] = city
    elif province:
        filters.append("province LIKE :province")
        params["province"] = f"%{province.rstrip('省市区')}%"
    where_sql = " AND ".join(filters)

    if "每月" in question or "每个月" in question or "按月" in question:
        rows = db.execute(
            text(
                f"""
                SELECT biz_month AS `月份`, ROUND(AVG(total_fee), 0) AS `平均运费`, COUNT(*) AS `记录数`
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY biz_month
                ORDER BY biz_month ASC
                """
            ),
            params,
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "route_monthly_avg_fee",
            "table": {"columns": ["月份", "平均运费"], "rows": table_rows},
            "summary_values": [row["平均运费"] for row in table_rows if row.get("平均运费") is not None],
        }

    if len(route_years) >= 2 or "分别" in question or "对比" in question:
        rows = db.execute(
            text(
                f"""
                SELECT biz_year AS `年份`, ROUND(AVG(total_fee), 0) AS `平均运费`, COUNT(*) AS `记录数`
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY biz_year
                ORDER BY biz_year ASC
                """
            ),
            params,
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "route_year_avg_fee",
            "table": {"columns": ["年份", "平均运费", "记录数"], "rows": table_rows},
            "summary_values": [row["平均运费"] for row in table_rows if row.get("平均运费") is not None],
        }

    if "最高价" in question or "最低价" in question:
        row = db.execute(
            text(
                f"""
                SELECT ROUND(MIN(total_fee), 0) AS `最低价`,
                       ROUND(MAX(total_fee), 0) AS `最高价`,
                       ROUND(AVG(total_fee), 0) AS `平均运费`,
                       COUNT(*) AS `记录数`
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                """
            ),
            params,
        ).mappings().first()
        payload = dict(row or {})
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "route_fee_extremes",
            "table": {"columns": ["最低价", "最高价", "平均运费", "记录数"], "rows": [payload]},
            "summary_values": [value for key, value in payload.items() if key != "记录数" and value is not None],
        }

    row = db.execute(
        text(
            f"""
            SELECT ROUND(AVG(total_fee), 0) AS `平均运费`, COUNT(*) AS `记录数`
            FROM dwd_logistics_hist_shipment_detail
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()
    payload = dict(row or {})
    return {
        "expected_status": "answerable",
        "answer_type": "table",
        "metric": "route_avg_fee",
        "table": {"columns": ["平均运费", "记录数"], "rows": [payload]},
        "summary_values": [payload.get("平均运费")] if payload.get("平均运费") is not None else [],
    }


def _build_hist_expected(db, item: dict[str, Any], years: list[int], months: list[int]) -> dict[str, Any]:
    """从历史物流明细表独立核算标准答案。"""
    question = item["question"]
    metric, unit, metric_label = _metric_for_question(question)
    if "吨" in question and any(word in question for word in ("发运量", "运量", "发货量")):
        return _clarification_expected("吨口径需要先确认吨重字段或换算规则，不能用 MW 口径替代。", ["吨重数据口径"])
    if any(word in question for word in ("多少量", "发运多少量")) and not any(word in question for word in ("发运量", "运量", "MW", "mw")):
        return _clarification_expected("“量”需要明确按 MW、吨、件数还是车次统计。", ["运量单位口径"])
    if "物流供应商" in question and "运量" in question and "发运量" not in question:
        return _clarification_expected("“物流供应商运量”需要确认按承运商发运量还是供应商主数据口径统计。", ["承运商口径", "运量单位"])
    if any(word in question for word in ("招标场景", "询比价场景", "经营计划场景", "辅料送样场景")):
        return _clarification_expected(
            "历史物流台账缺少稳定采购方式/业务场景字段，不能按招标、询比价、经营计划或辅料送样场景直接拆分统计。",
            ["业务场景字段口径", "历史数据映射规则"],
        )
    if "17.5" in question and any(word in question for word in ("多少车", "发出了多少车", "发运多少车")):
        year_clause = ", ".join(str(int(year)) for year in years)
        # 用户指定“合肥/阜宁基地”时，独立标准答案必须同步下推始发基地；
        # 否则会把基地车型车次误算成全年全基地车型车次。
        special_origin_place = _origin_place_filter(question)
        origin_sql = " AND origin_place = :origin_place" if special_origin_place else ""
        params = {"origin_place": special_origin_place} if special_origin_place else {}
        row = db.execute(
            text(
                f"""
                SELECT ROUND(SUM(COALESCE(shipment_trip_count, 0)), 0) AS trip_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_clause})
                  AND required_vehicle_type LIKE '%17.5%'
                  {origin_sql}
                """
            ),
            params,
        ).mappings().first()
        trip_count = int(float((row or {}).get("trip_count") or 0))
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "shipment_trip_count",
            "table": {"columns": ["车次"], "rows": [{"车次": trip_count}]},
            "summary_values": [trip_count],
        }
    if "合肥" in question and "江苏" in question and "17.5" in question and "运费" in question:
        row = db.execute(
            text(
                """
                SELECT ROUND(AVG(total_fee), 0) AS avg_fee, COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE required_vehicle_type LIKE '%17.5%'
                  AND origin_place = '合肥'
                  AND province LIKE '%江苏%'
                """
            )
        ).mappings().first()
        avg_fee = _decimal_to_float((row or {}).get("avg_fee"))
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "avg_fee",
            "table": {"columns": ["平均运费", "记录数"], "rows": [{"平均运费": avg_fee, "记录数": int((row or {}).get("row_count") or 0)}]},
            "summary_values": [avg_fee],
        }
    route_expected = _build_hist_route_pricing_expected(db, question, years)
    if route_expected:
        return route_expected
    if "乌鲁木齐" in question and ("13m" in question.lower() or "13" in question) and any(word in question for word in ("均价", "平均")):
        year_clause = ", ".join(str(int(year)) for year in years)
        row = db.execute(
            text(
                f"""
                SELECT ROUND(AVG(total_fee), 0) AS avg_fee, COUNT(*) AS row_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_clause})
                  AND city = '乌鲁木齐'
                  AND required_vehicle_type LIKE '%13%'
                """
            )
        ).mappings().first()
        avg_fee = _decimal_to_float((row or {}).get("avg_fee"))
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "avg_fee",
            "table": {"columns": ["平均运费", "记录数"], "rows": [{"平均运费": avg_fee, "记录数": int((row or {}).get("row_count") or 0)}]},
            "summary_values": [avg_fee],
        }
    if "额外费用占总费用比重最高" in question:
        year_clause = ", ".join(str(int(year)) for year in years)
        rows = db.execute(
            text(
                f"""
                SELECT biz_month AS `月份`,
                       ROUND(SUM(COALESCE(extra_fee, 0)), 2) AS `额外费用`,
                       ROUND(SUM(COALESCE(total_fee, 0)), 2) AS `总费用`,
                       ROUND(SUM(COALESCE(extra_fee, 0)) / NULLIF(SUM(COALESCE(total_fee, 0)), 0) * 100, 2) AS `额外费用占比`
                FROM dwd_logistics_hist_shipment_detail
                WHERE biz_year IN ({year_clause})
                GROUP BY biz_month
                ORDER BY `额外费用占比` DESC
                LIMIT 1
                """
            ),
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "extra_fee_share",
            "table": {"columns": ["月份", "额外费用", "总费用", "额外费用占比"], "rows": table_rows},
            "summary_values": [
                value
                for row in table_rows
                for value in (row.get("月份"), row.get("额外费用"), row.get("额外费用占比"))
                if value is not None
            ],
        }
    if "同一客户由多个始发地" in question:
        year_clause = ", ".join(str(int(year)) for year in years)
        effective_customer_sql = """
            JSON_UNQUOTE(JSON_EXTRACT(raw_row_json, '$."客户名称（标准名称；最终客户）"'))
        """
        rows = db.execute(
            text(
                f"""
                SELECT effective_customer_name AS `客户`, COUNT(DISTINCT origin_place) AS `始发地数量`
                FROM (
                    SELECT {effective_customer_sql} AS effective_customer_name, origin_place
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE biz_year IN ({year_clause})
                ) base
                WHERE effective_customer_name IS NOT NULL AND TRIM(effective_customer_name) <> ''
                GROUP BY effective_customer_name
                HAVING COUNT(DISTINCT origin_place) > 1
                ORDER BY `始发地数量` DESC, effective_customer_name ASC
                LIMIT 50
                """
            )
        ).mappings().all()
        count_row = db.execute(
            text(
                f"""
                SELECT COUNT(*) AS customer_count
                FROM (
                    SELECT effective_customer_name
                    FROM (
                        SELECT {effective_customer_sql} AS effective_customer_name, origin_place
                        FROM dwd_logistics_hist_shipment_detail
                        WHERE biz_year IN ({year_clause})
                    ) base
                    WHERE effective_customer_name IS NOT NULL AND TRIM(effective_customer_name) <> ''
                    GROUP BY effective_customer_name
                    HAVING COUNT(DISTINCT origin_place) > 1
                ) t
                """
            )
        ).mappings().first()
        table_rows = [dict(row) for row in rows]
        customer_count = int((count_row or {}).get("customer_count") or 0)
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "multi_origin_customer_count",
            "table": {"columns": ["客户", "始发地数量"], "rows": table_rows},
            "summary_values": [customer_count] + [row.get("客户") for row in table_rows[:5] if row.get("客户")],
        }
    if "水路记录" in question:
        row = db.execute(
            text(
                """
                SELECT COUNT(*) AS waterway_count,
                       (SELECT COUNT(*) FROM dwd_logistics_hist_shipment_detail) AS total_count
                FROM dwd_logistics_hist_shipment_detail
                WHERE transport_mode = '水路'
                """
            )
        ).mappings().first()
        waterway_count = int((row or {}).get("waterway_count") or 0)
        total_count = int((row or {}).get("total_count") or 0)
        ratio = round(waterway_count / total_count * 100, 2) if total_count else 0
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "waterway_record_count",
            "table": {
                "columns": ["运输方式", "记录数", "全部记录数", "占比"],
                "rows": [{"运输方式": "水路", "记录数": waterway_count, "全部记录数": total_count, "占比": ratio}],
            },
            "summary_values": [waterway_count, ratio],
        }
    if any(word in question for word in ("发运达标率", "达标率")):
        return _clarification_expected("达标率需要先确认业务公式和计算颗粒度。", ["达标率口径", "统计颗粒度"])
    if any(word in question for word in ("额外费用", "异常费")) and any(word in question for word in ("明细", "原因", "项目")):
        return _unsupported_expected("当前系统仅支持额外费用总额统计，尚未固化费用明细、原因和项目归因口径。")
    if "异常" in question and not any(word in question for word in ("异常费用", "额外费用")):
        return _clarification_expected("异常判断需要先明确异常指标和时间范围。", ["异常判定口径", "时间范围"])
    if "总件数" in question or "平均路程" in question or "平均送达距离" in question:
        return _clarification_expected("当前问题涉及件数或距离口径，需要先确认稳定字段和单位。", ["字段口径", "单位"])
    if "平均元/瓦" in question and any(word in question for word in ("差值", "哪个更高", "高多少")):
        return _clarification_expected("跨对象平均元/瓦对比需要先确认分子分母汇总口径。", ["平均元/瓦计算口径"])
    if any(word in question for word in ("相关性", "显著")):
        return _unsupported_expected("当前系统不做统计显著性或相关性检验。")
    if any(word in question for word in ("单价/车最高", "长距离订单", "产生原因", "超计划比例", "份额变化", "更偏好")):
        return _clarification_expected("该类复杂分析题需要先确认排名、归并或业务判断口径。", ["分析口径"])
    if "询比价" in question and "招标" in question and "超过20万" in question:
        return _unsupported_expected("历史台账缺少稳定采购方式字段，不能按询比价/招标拆分发运量。")
    if "平均每车装载托数" in question or "装载托数" in question or "托数" in question:
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": "平均每车装载托数需要先确认按车次、任务还是装载记录平均，以及空值处理口径。",
            "missing_slots": ["装载托数统计口径"],
        }
    dims = _dimensions_for_question(question)
    top_n = extract_top_n(question)
    year_clause = ", ".join(str(int(year)) for year in years)
    filters = [f"biz_year IN ({year_clause})"]
    params: dict[str, Any] = {}
    if months:
        month_clause = ", ".join(str(int(month)) for month in months)
        filters.append(f"biz_month IN ({month_clause})")
    province = _province_filter(question)
    if province:
        filters.append("province LIKE :province")
        params["province"] = f"%{province.rstrip('省市区')}%"
        dims = [dimension for dimension in dims if dimension[0] != "province"]
    region = _region_filter(question)
    if region:
        filters.append("region_name LIKE :region")
        params["region"] = f"%{region}%"
        dims = [dimension for dimension in dims if dimension[0] != "region_name"]
    origin_place = _origin_place_filter(question)
    if origin_place:
        filters.append("origin_place = :origin_place")
        params["origin_place"] = origin_place
        dims = [dimension for dimension in dims if dimension[0] != "origin_place"]
    carrier = _carrier_filter(question)
    if carrier:
        filters.append("logistics_company_name LIKE :carrier")
        params["carrier"] = f"%{carrier}%"
        dims = [dimension for dimension in dims if dimension[0] != "logistics_company_name"]
    customer = _customer_filter(question)
    if customer:
        filters.append("customer_name LIKE :customer")
        params["customer"] = f"%{customer}%"
        dims = [dimension for dimension in dims if dimension[0] != "customer_name"]
    product_spec = _product_spec_filter(question)
    if product_spec:
        filters.append("product_spec LIKE :product_spec")
        params["product_spec"] = f"%{product_spec}%"
        dims = [dimension for dimension in dims if dimension[0] != "product_spec"]
    transport_mode = _transport_mode_filter(question)
    if transport_mode:
        filters.append("transport_mode = :transport_mode")
        params["transport_mode"] = transport_mode
        dims = [dimension for dimension in dims if dimension[0] != "transport_mode"]
    vehicle_type = _vehicle_type_filter(question)
    if vehicle_type:
        filters.append("required_vehicle_type LIKE :vehicle_type")
        params["vehicle_type"] = f"%{vehicle_type}%"
        dims = [dimension for dimension in dims if dimension[0] != "required_vehicle_type"]
    city = _city_filter(question)
    if city:
        filters.append("city LIKE :city")
        params["city"] = f"%{city}%"
        dims = [dimension for dimension in dims if dimension[0] != "city"]
    where_sql = " AND ".join(filters)
    if _is_hist_origin_vehicle_breakdown_question(question):
        # 与正式问答链路的 hist_origin_vehicle_breakdown_summary 保持同一口径：
        # 已校验始发地则过滤始发地；无法校验的“始发地”表达保留真实源数据始发地分组。
        breakdown_dims = [("required_vehicle_type", "车型")]
        if not origin_place:
            breakdown_dims.insert(0, ("origin_place", "始发地"))
        select_dims = ", ".join(f"{column} AS `{label}`" for column, label in breakdown_dims)
        group_by = ", ".join(column for column, _label in breakdown_dims)
        rows = db.execute(
            text(
                f"""
                SELECT
                    {select_dims},
                    ROUND(SUM(COALESCE(shipment_trip_count, 0)), 0) AS trip_count,
                    ROUND(SUM(COALESCE(total_fee, 0)), 2) AS total_fee,
                    ROUND(SUM(COALESCE(total_fee, 0)) / NULLIF(SUM(COALESCE(shipment_trip_count, 0)), 0), 2) AS avg_fee_per_trip
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY {group_by}
                ORDER BY total_fee DESC
                """
            ),
            params,
        ).mappings().all()
        table_rows: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["发运车次"] = _decimal_to_float(item.pop("trip_count"))
            item["总运费"] = _decimal_to_float(item.pop("total_fee"))
            item["平均单车费用"] = _decimal_to_float(item.pop("avg_fee_per_trip"))
            table_rows.append(item)
        summary_values: list[Any] = []
        for row in table_rows:
            summary_values.extend([row.get("发运车次"), row.get("总运费"), row.get("平均单车费用")])
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "origin_vehicle_breakdown",
            "metric_label": "车型汇总",
            "unit": "混合单位",
            "filters": {
                "years": years,
                "months": months,
                "origin_place": origin_place,
                "city": city,
            },
            "dimensions": [label for _column, label in breakdown_dims],
            "table": {
                "columns": [label for _column, label in breakdown_dims] + ["发运车次", "总运费", "平均单车费用"],
                "rows": table_rows,
            },
            "summary_values": [value for value in summary_values if value is not None],
        }
    if metric == "avg_fee_per_watt" and any(column == "transport_mode" for column, _label in dims):
        rows = db.execute(
            text(
                f"""
                SELECT
                    CASE WHEN transport_mode IN ('汽运', '公路') THEN '公路' ELSE transport_mode END AS `运输方式`,
                    ROUND(AVG(fee_per_watt), 4) AS value
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                  AND fee_per_watt IS NOT NULL
                GROUP BY CASE WHEN transport_mode IN ('汽运', '公路') THEN '公路' ELSE transport_mode END
                ORDER BY value ASC
                """
            ),
            params,
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        for row in table_rows:
            row[metric_label] = _decimal_to_float(row.pop("value"))
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": metric,
            "metric_label": metric_label,
            "unit": unit,
            "filters": {
                "years": years,
                "months": months,
                "province": province,
                "region": region,
                "origin_place": origin_place,
                "carrier": carrier,
                "customer": customer,
                "product_spec": product_spec,
                "transport_mode": transport_mode,
                "city": city,
            },
            "dimensions": ["运输方式"],
            "top_n": top_n,
            "table": {"columns": ["运输方式", metric_label], "rows": table_rows},
            "summary_values": [row[metric_label] for row in table_rows if row.get(metric_label) is not None],
        }
    metric_sql = {
        "total_fee": "ROUND(SUM(COALESCE(total_fee, 0)), 2)",
        "actual_watt": "ROUND(SUM(COALESCE(actual_watt, 0)) / 1000000, 4)",
        "actual_qty": "ROUND(SUM(COALESCE(actual_qty, 0)), 2)",
        # “平均运费/平均运输费用”按历史明细 total_fee 直接做样本平均，
        # 与物流主链路的 hist_origin_destination_metric_query(avg_fee) 口径保持一致。
        "avg_fee": "ROUND(AVG(total_fee), 0)",
        # 无分组的“平均单瓦成本”按总费用 / 总瓦数核算，和正式问答链路保持一致；
        # 按运输方式分组排名的题族仍在上方专用分支使用 AVG(fee_per_watt)。
        "avg_fee_per_watt": "ROUND(SUM(COALESCE(total_fee, 0)) / NULLIF(SUM(actual_watt), 0), 8)",
        # “平均单瓦价/单瓦价”按总费用除以总瓦数，和主链路 hist_origin_vehicle_metric_summary 保持一致。
        "unit_fee_per_watt": "ROUND(SUM(COALESCE(total_fee, 0)) / NULLIF(SUM(actual_watt), 0), 8)",
        "avg_fee_per_trip": "ROUND(SUM(COALESCE(total_fee, 0)) / NULLIF(SUM(shipment_trip_count), 0), 0)",
        "record_count": "COUNT(*)",
        "shipment_trip_count": "ROUND(SUM(COALESCE(shipment_trip_count, 0)), 2)",
        "extra_fee": "ROUND(SUM(COALESCE(extra_fee, 0)), 2)",
    }[metric]
    if dims:
        select_dims = ", ".join(f"{column} AS `{label}`" for column, label in dims)
        group_by = ", ".join(column for column, _label in dims)
        limit_sql = " LIMIT :limit_value" if top_n else ""
        if top_n:
            params["limit_value"] = top_n
        rows = db.execute(
            text(
                f"""
                SELECT {select_dims}, {metric_sql} AS value
                FROM dwd_logistics_hist_shipment_detail
                WHERE {where_sql}
                GROUP BY {group_by}
                ORDER BY value DESC
                {limit_sql}
                """
            ),
            params,
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        for row in table_rows:
            row[metric_label] = _decimal_to_float(row.pop("value"))
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": metric,
            "metric_label": metric_label,
            "unit": unit,
            "filters": {
                "years": years,
                "months": months,
                "province": province,
                "region": region,
                "origin_place": origin_place,
                "carrier": carrier,
                "customer": customer,
                "product_spec": product_spec,
                "transport_mode": transport_mode,
                "vehicle_type": vehicle_type,
                "city": city,
            },
            "dimensions": [label for _column, label in dims],
            "top_n": top_n,
            "table": {
                "columns": [label for _column, label in dims] + [metric_label],
                "rows": table_rows,
            },
            "summary_values": [row[metric_label] for row in table_rows if row.get(metric_label) is not None],
        }
    row = db.execute(
        text(
            f"""
            SELECT {metric_sql} AS value, COUNT(*) AS row_count
            FROM dwd_logistics_hist_shipment_detail
            WHERE {where_sql}
            """
        ),
        params,
    ).mappings().first()
    value = _decimal_to_float(row["value"] if row else None)
    return {
        "expected_status": "answerable",
        "answer_type": "numeric",
        "metric": metric,
        "metric_label": metric_label,
        "unit": unit,
        "filters": {
            "years": years,
            "months": months,
            "province": province,
            "region": region,
            "origin_place": origin_place,
            "carrier": carrier,
            "customer": customer,
            "product_spec": product_spec,
            "transport_mode": transport_mode,
            "vehicle_type": vehicle_type,
            "city": city,
        },
        "value": value,
        "row_count": int((row or {}).get("row_count") or 0),
        "summary_values": [value] if value is not None else [],
    }


def _build_sys_expected(db, item: dict[str, Any], years: list[int], months: list[int]) -> dict[str, Any]:
    """从 2026 系统中间库独立核算标准答案。"""
    question = item["question"]
    metric, unit, metric_label = _metric_for_question(question)
    dims = _dimensions_for_question(question)
    top_n = extract_top_n(question)
    year_clause = ", ".join(str(int(year)) for year in years)
    filters = [f"st.biz_year IN ({year_clause})"]
    params: dict[str, Any] = {}
    if months:
        month_clause = ", ".join(str(int(month)) for month in months)
        filters.append(f"MONTH(COALESCE(st.pickup_date, st.biz_date)) IN ({month_clause})")
    province = _province_filter(question)
    if province:
        filters.append("st.delivery_province LIKE :province")
        params["province"] = f"%{province.rstrip('省市区')}%"
        dims = [dimension for dimension in dims if dimension[0] != "province"]
    region = _region_filter(question)
    if region:
        filters.append("st.normalized_region_name LIKE :region")
        params["region"] = f"%{region}%"
        dims = [dimension for dimension in dims if dimension[0] != "region_name"]
    product_spec = _product_spec_filter(question)
    if product_spec:
        filters.append("sp.product_spec LIKE :product_spec")
        params["product_spec"] = f"%{product_spec}%"
        dims = [dimension for dimension in dims if dimension[0] != "product_spec"]
    customer_name = _sys_customer_filter(question)
    if customer_name:
        filters.append("st.project_name LIKE :customer_name")
        params["customer_name"] = f"%{customer_name}%"
    company_name = _sys_company_filter(question)
    if company_name:
        filters.append("st.company_name LIKE :company_name")
        params["company_name"] = f"%{company_name}%"
    procurement_type = _sys_procurement_type_filter(question)
    if procurement_type:
        filters.append("st.procurement_type = :procurement_type")
        params["procurement_type"] = procurement_type
    base_code = _sys_base_code_filter(question)
    if base_code:
        filters.append("st.base_code = :base_code")
        params["base_code"] = base_code
    transport_mode = _transport_mode_filter(question)
    if transport_mode:
        filters.append("st.transport_mode = :transport_mode")
        params["transport_mode"] = transport_mode
        # 用户已经把运输方式作为过滤条件时，标准答案不再要求前端表格额外展示“运输方式”列。
        dims = [dimension for dimension in dims if dimension[0] != "transport_mode"]
    special_scope = None
    if "经营计划" in question or "经营计划部" in question:
        special_scope = "planning"
    elif "辅料送样" in question:
        special_scope = "sample"
    elif "刘娟" in question:
        special_scope = "liujuan"
    if special_scope:
        special_filter_sql = {
            "planning": "st.expand_dept IN ('经营计划', '经营计划部')",
            "sample": "st.ship_type = '2'",
            "liujuan": "st.entrusted_person = '刘娟'",
        }[special_scope]
        filters.append(special_filter_sql)
    where_sql = " AND ".join(filters)
    if "为什么可能不一致" in question and any(word in question for word in ("客户名", "项目")):
        return _clarification_expected(
            "这是字段口径解释题，需要先确认按客户名称、项目名称，还是归一后的客户口径查询；系统不能把两个不同字段表达直接混为同一个统计条件。",
            ["客户字段口径", "项目字段口径", "客户归一规则"],
        )
    if any(word in question for word in ("身份证", "手机号")):
        return _clarification_expected("司机身份与手机号一致性检查需要先确认字段来源、异常定义和输出口径。", ["司机主数据口径", "异常判定标准"])
    if "额外费用" in question and any(word in question for word in ("项目", "原因", "明细")):
        return _unsupported_expected("当前系统只支持额外费用总额，不支持项目、原因和明细归因。")
    if "平均送达距离" in question or "平均距离" in question:
        return _clarification_expected("平均送达距离需要先确认距离字段来源和运输方式同义口径。", ["距离字段口径"])
    if "采购方式" in question and "任务量" in question:
        rows = db.execute(
            text(
                """
                SELECT procurement_type AS `采购方式`,
                       COUNT(*) AS `任务数`,
                       ROUND(COUNT(*) / NULLIF(SUM(COUNT(*)) OVER (), 0) * 100, 2) AS `任务占比`
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND procurement_type IS NOT NULL
                  AND TRIM(procurement_type) <> ''
                GROUP BY procurement_type
                ORDER BY `任务数` DESC, procurement_type ASC
                """
            ),
            {"year": years[0]},
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "procurement_task_distribution",
            "table": {"columns": ["采购方式", "任务数", "任务占比"], "rows": table_rows},
            "summary_values": [value for row in table_rows for value in (row.get("采购方式"), row.get("任务数"), row.get("任务占比")) if value is not None],
        }
    if ("采购方式" in question or ("招标" in question and "询比价" in question)) and _metric_for_question(question)[0] == "actual_watt":
        rows = db.execute(
            text(
                """
                SELECT COALESCE(NULLIF(TRIM(procurement_type), ''), '未填充') AS `采购方式`,
                       ROUND(SUM(CASE WHEN power IS NOT NULL THEN power * quantity ELSE 0 END) / 1000000, 3) AS `发运量`,
                       COUNT(DISTINCT st.task_id) AS `任务数`
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                WHERE st.biz_year = :year
                GROUP BY `采购方式`
                ORDER BY `发运量` DESC, `采购方式` ASC
                """
            ),
            {"year": years[0]},
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "procurement_shipment_mw",
            "table": {"columns": ["采购方式", "发运量", "任务数"], "rows": table_rows},
            "summary_values": [value for row in table_rows for value in (row.get("采购方式"), row.get("发运量"), row.get("任务数")) if value is not None],
        }
    if metric in {"avg_fee_per_watt", "unit_fee_per_watt"} and any(word in question for word in ("承运商", "物流公司", "各物流")) and top_n:
        # 2026 承运商单瓦成本排名按正式链路相同口径独立核算：
        # 单瓦成本 = 系统总运费 / 发运瓦数，排序取前 N。
        limit_value = top_n or 10
        rows = db.execute(
            text(
                f"""
                WITH task_fee AS (
                    SELECT
                        st.task_id,
                        st.company_name,
                        CASE
                            WHEN {PROJECT_TOTAL_TRUCKS_SQL} IS NOT NULL AND MAX(sp.price) IS NOT NULL
                                THEN MAX(sp.price) * {PROJECT_TOTAL_TRUCKS_SQL}
                            ELSE 0
                        END AS task_total_fee
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
                    WHERE {where_sql}
                      AND st.company_name IS NOT NULL
                      AND TRIM(st.company_name) <> ''
                    GROUP BY st.task_id, st.company_name, st.project_name
                ),
                fee_scope AS (
                    SELECT
                        company_name,
                        ROUND(SUM(task_total_fee), 2) AS total_fee,
                        COUNT(*) AS task_count
                    FROM task_fee
                    GROUP BY company_name
                ),
                mw_scope AS (
                    SELECT
                        st.company_name,
                        ROUND(SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) / 1000000, 3) AS shipment_mw,
                        SUM(CASE WHEN sp.power IS NOT NULL THEN sp.power * sp.quantity ELSE 0 END) AS shipment_watt
                    FROM dwd_logistics_ship_product sp
                    JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                    WHERE {where_sql}
                      AND st.company_name IS NOT NULL
                      AND TRIM(st.company_name) <> ''
                    GROUP BY st.company_name
                )
                SELECT
                    fee_scope.company_name AS `承运商`,
                    ROUND(fee_scope.total_fee / NULLIF(mw_scope.shipment_watt, 0), 8) AS `平均元/瓦`,
                    fee_scope.total_fee AS `总运费`,
                    mw_scope.shipment_mw AS `发运量`,
                    fee_scope.task_count AS `任务数`
                FROM fee_scope
                JOIN mw_scope ON mw_scope.company_name = fee_scope.company_name
                ORDER BY `平均元/瓦` DESC, `总运费` DESC, `承运商` ASC
                LIMIT :limit_value
                """
            ),
            {**params, "limit_value": limit_value},
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "unit_fee_per_watt",
            "metric_label": "平均元/瓦",
            "unit": "元/瓦",
            "filters": {"years": years, "months": months, "province": province, "region": region},
            "dimensions": ["承运商"],
            "top_n": limit_value,
            "table": {"columns": ["承运商", "平均元/瓦", "总运费", "发运量", "任务数"], "rows": table_rows},
            "summary_values": [
                value
                for row in table_rows
                for value in (row.get("承运商"), row.get("平均元/瓦"), row.get("总运费"), row.get("发运量"), row.get("任务数"))
                if value is not None
            ],
        }
    if "送达城市任务量排名前十" in question:
        rows = db.execute(
            text(
                """
                SELECT delivery_city AS `送达城市`, COUNT(*) AS `任务数`
                FROM dwd_logistics_ship_task
                WHERE biz_year = :year
                  AND delivery_city IS NOT NULL
                  AND TRIM(delivery_city) <> ''
                GROUP BY delivery_city
                ORDER BY `任务数` DESC, delivery_city ASC
                LIMIT 10
                """
            ),
            {"year": years[0]},
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "delivery_city_task_count_top10",
            "table": {"columns": ["送达城市", "任务数"], "rows": table_rows},
            "summary_values": [value for row in table_rows for value in (row.get("送达城市"), row.get("任务数")) if value is not None],
        }
    if metric == "actual_watt" and "车次" in question:
        pickup_expr = "COALESCE(st.pickup_date, STR_TO_DATE(JSON_UNQUOTE(JSON_EXTRACT(ost.raw_json, '$.pickup_date')), '%Y-%m-%d'))"
        month_filter = ""
        if months:
            month_filter = " AND MONTH({pickup_expr}) IN ({months})".format(
                pickup_expr=pickup_expr,
                months=", ".join(str(int(month)) for month in months),
            )
        mw_value = db.execute(
            text(
                f"""
                SELECT ROUND(SUM(sp.power * sp.quantity) / 1000000, 3)
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({pickup_expr}) = :year
                  {month_filter}
                  AND sp.power IS NOT NULL
                """
            ),
            {"year": years[0]},
        ).scalar()
        trip_value = db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dwd_logistics_assign_task at
                JOIN dwd_logistics_ship_task st ON st.task_id = at.ship_task_id
                LEFT JOIN ods_logistic_ship_task ost ON ost.task_id = st.task_id
                WHERE YEAR({pickup_expr}) = :year
                  {month_filter}
                  AND at.status IN ('ENTER', 'LEAVE')
                """
            ),
            {"year": years[0]},
        ).scalar()
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "sys_mw_and_trip_count",
            "table": {"columns": ["发运量", "车次"], "rows": [{"发运量": _decimal_to_float(mw_value), "车次": int(trip_value or 0)}]},
            "summary_values": [_decimal_to_float(mw_value), int(trip_value or 0)],
        }
    if metric == "actual_watt":
        mw_value = db.execute(
            text(
                f"""
                SELECT ROUND(SUM(sp.power * sp.quantity) / 1000000, 3)
                FROM dwd_logistics_ship_product sp
                JOIN dwd_logistics_ship_task st ON st.task_id = sp.task_id
                WHERE {where_sql}
                  AND sp.power IS NOT NULL
                """
            ),
            params,
        ).scalar()
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": "sys_shipment_mw",
            "table": {"columns": ["发运量"], "rows": [{"发运量": _decimal_to_float(mw_value)}]},
            "summary_values": [_decimal_to_float(mw_value)],
        }
    if metric != "total_fee":
        if metric == "extra_fee":
            row = db.execute(
                text(
                    f"""
                    SELECT
                        ROUND(SUM(COALESCE(ad.extra_cost, 0)), 2) AS value,
                        COUNT(DISTINCT st.task_id) AS task_count,
                        COUNT(ad.id) AS detail_count
                    FROM dwd_logistics_ship_task st
                    LEFT JOIN dwd_logistics_assign_detail ad ON ad.ship_task_id = st.task_id
                    WHERE {where_sql}
                    """
                ),
                params,
            ).mappings().first()
            value = _decimal_to_float((row or {}).get("value"))
            return {
                "expected_status": "answerable",
                "answer_type": "numeric",
                "metric": "extra_fee",
                "metric_label": "额外费用",
                "unit": "元",
                "filters": {"years": years, "months": months, "province": province, "region": region},
                "value": value,
                "row_count": int((row or {}).get("task_count") or 0),
                "summary_values": [value] if value is not None else [],
            }
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": "2026 系统题当前独立核算层只稳定支持总运费、发运量、额外费用和已验证的承运商单瓦成本排名，其他指标需要进一步确认系统字段口径。",
            "missing_slots": ["2026系统指标口径"],
        }
    dim_selects: list[str] = []
    group_parts: list[str] = []
    for column, label in dims:
        if column == "biz_month":
            expr = "DATE_FORMAT(COALESCE(st.pickup_date, st.biz_date), '%Y-%m')"
        elif column == "logistics_company_name":
            expr = "st.company_name"
        elif column == "province":
            expr = "st.delivery_province"
        elif column == "city":
            expr = "st.delivery_city"
        elif column == "region_name":
            expr = "st.normalized_region_name"
        elif column == "transport_mode":
            expr = "st.transport_mode"
        else:
            continue
        dim_selects.append(f"{expr} AS `{label}`")
        group_parts.append(expr)

    task_cte = f"""
        WITH task_product AS (
            SELECT
                st.task_id,
                st.project_name,
                {', '.join(dim_selects) + ',' if dim_selects else ''}
                {PROJECT_TOTAL_TRUCKS_SQL} AS total_truck_count,
                MAX(sp.price) AS car_price
            FROM dwd_logistics_ship_task st
            LEFT JOIN dwd_logistics_ship_product sp ON sp.task_id = st.task_id
            WHERE {where_sql}
            GROUP BY st.task_id, st.project_name{', ' + ', '.join(group_parts) if group_parts else ''}
        )
    """
    total_expr = "ROUND(SUM(CASE WHEN total_truck_count IS NOT NULL AND car_price IS NOT NULL THEN car_price * total_truck_count ELSE 0 END), 2)"
    if dim_selects:
        labels = [label for _column, label in dims if label in "".join(dim_selects)]
        limit_sql = " LIMIT :limit_value" if top_n else ""
        if top_n:
            params["limit_value"] = top_n
        rows = db.execute(
            text(
                f"""
                {task_cte}
                SELECT {', '.join(f'`{label}`' for label in labels)}, {total_expr} AS value,
                       COUNT(*) AS task_count
                FROM task_product
                GROUP BY {', '.join(f'`{label}`' for label in labels)}
                ORDER BY value DESC
                {limit_sql}
                """
            ),
            params,
        ).mappings().all()
        table_rows = [dict(row) for row in rows]
        for row in table_rows:
            row[metric_label] = _decimal_to_float(row.pop("value"))
            row["任务数"] = row.pop("task_count")
        return {
            "expected_status": "answerable",
            "answer_type": "table",
            "metric": metric,
            "metric_label": metric_label,
            "unit": unit,
            "filters": {"years": years, "months": months, "province": province, "region": region},
            "dimensions": labels,
            "top_n": top_n,
            "table": {"columns": labels + [metric_label, "任务数"], "rows": table_rows},
            "summary_values": [row[metric_label] for row in table_rows if row.get(metric_label) is not None],
        }
    row = db.execute(
        text(
            f"""
            {task_cte}
            SELECT {total_expr} AS value,
                   COUNT(*) AS task_count,
                   SUM(CASE WHEN total_truck_count IS NULL THEN 1 ELSE 0 END) AS parse_fail_count,
                   SUM(CASE WHEN car_price IS NULL THEN 1 ELSE 0 END) AS price_missing_count
            FROM task_product
            """
        ),
        params,
    ).mappings().first()
    value = _decimal_to_float(row["value"] if row else None)
    return {
        "expected_status": "answerable",
        "answer_type": "numeric",
        "metric": metric,
        "metric_label": metric_label,
        "unit": unit,
        "filters": {"years": years, "months": months, "province": province, "region": region},
        "value": value,
        "row_count": int((row or {}).get("task_count") or 0),
        "warnings": {
            "parse_fail_count": int((row or {}).get("parse_fail_count") or 0),
            "price_missing_count": int((row or {}).get("price_missing_count") or 0),
        },
        "summary_values": [value] if value is not None else [],
    }


def _load_bom_materials() -> list[dict[str, Any]]:
    """读取真实 BOM 标准化材料数据。"""
    path = PROJECT_ROOT / "tmp" / "plan_bom" / "plan_bom_standardized_materials.json"
    if not path.exists():
        return []
    return read_json(path, default=[])


def _extract_order_tails(question: str) -> list[str]:
    """从 BOM 问题中提取订单尾号或完整订单号片段。"""
    import re

    tails = re.findall(r"(?:20\d{2}[-_])?(\d{5})", question)
    return sorted(set(tails))


def _extract_material_categories(question: str) -> list[str]:
    """从 BOM 问题中提取材料类别。"""
    categories = []
    for category, aliases in MATERIAL_ALIASES.items():
        if any(alias.lower() in question.lower() for alias in aliases):
            categories.append(category)
    return categories


def _build_bom_expected(item: dict[str, Any], materials: list[dict[str, Any]]) -> dict[str, Any]:
    """基于真实 BOM 标准化数据核算标准答案。"""
    question = item["question"]
    tails = _extract_order_tails(question)
    categories = _extract_material_categories(question)
    is_compare = item.get("question_type") == "bom_compare" or "对比" in question or "不一样" in question
    if "功率" in question and "电池" in question:
        return {
            "expected_status": "unsupported",
            "answer_type": "unsupported",
            "reason": "当前 BOM 数据不包含功率倒推规则和电池方案预测模型，不能直接回答。",
        }
    if not tails and any(word in question for word in ["多个订单", "所有", "哪些订单", "全部订单"]):
        # 范围类题可以基于现有全部订单做表格，但这里只限制材料类别，避免误把业务范围不清硬算。
        if not categories:
            return {
                "expected_status": "needs_clarification",
                "answer_type": "clarification",
                "reason": "缺少材料范围或订单范围。",
                "missing_slots": ["材料范围", "订单范围"],
            }
    elif not tails:
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": "缺少可校验订单号或订单尾号。",
            "missing_slots": ["订单号"],
        }
    if not categories:
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": "缺少材料类别。",
            "missing_slots": ["材料类别"],
        }

    identity_by_tail: dict[str, set[str]] = {}
    for tail in tails:
        identity_by_tail[tail] = {
            str(row.get("order_identity_key") or "")
            for row in materials
            if str(row.get("order_no") or "").endswith(tail) and row.get("order_identity_key")
        }
    ambiguous_tails = [tail for tail, identities in identity_by_tail.items() if len(identities) > 1]
    if ambiguous_tails:
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": f"订单尾号 {', '.join(ambiguous_tails)} 命中多个 BOM 业务实例，需要补充客户、国家、型号或完整订单名。",
            "missing_slots": ["订单业务实例"],
        }
    if is_compare and len(set(tails)) < 2:
        return {
            "expected_status": "needs_clarification",
            "answer_type": "clarification",
            "reason": "对比类问题需要至少两个不同订单或两个不同版本。",
            "missing_slots": ["对比对象"],
        }

    selected_versions: dict[str, str] = {}
    for tail, identities in identity_by_tail.items():
        if not identities:
            continue
        identity = next(iter(identities))
        versions = {
            str(row.get("version_no") or "")
            for row in materials
            if row.get("order_identity_key") == identity and row.get("version_no")
        }
        selected_versions[identity] = sorted(versions, key=_version_rank, reverse=True)[0] if versions else ""

    matched_rows = []
    for row in materials:
        order_no = str(row.get("order_no") or "")
        if tails and not any(order_no.endswith(tail) or tail in order_no for tail in tails):
            continue
        identity = str(row.get("order_identity_key") or "")
        if identity and selected_versions.get(identity) and str(row.get("version_no") or "") != selected_versions[identity]:
            continue
        if row.get("material_category") not in categories:
            continue
        matched_rows.append(
            {
                "订单号": order_no,
                "版本": row.get("version_no"),
                "材料类别": row.get("material_category"),
                "物料名称": row.get("material_name"),
                "规格描述": row.get("description"),
                "用量": row.get("standard_usage"),
                "单位": row.get("unit"),
            }
        )
    if not matched_rows:
        return {
            "expected_status": "answerable",
            "answer_type": "empty_result",
            "orders": tails,
            "material_categories": categories,
            "table": {"columns": ["订单号", "版本", "材料类别", "物料名称", "规格描述", "用量", "单位"], "rows": []},
        }
    bom_table_columns = ["订单号", "版本", "材料类别", "物料名称", "规格描述", "用量", "单位"]
    summary_values = [row["规格描述"] for row in matched_rows if row.get("规格描述")]
    if is_compare and len(tails) >= 2:
        rows_by_tail: dict[str, list[dict[str, Any]]] = {}
        for row in matched_rows:
            order_no = str(row.get("订单号") or "")
            for tail in tails:
                if order_no.endswith(tail) or tail in order_no:
                    rows_by_tail.setdefault(tail, []).append(row)
        if len(rows_by_tail) >= 2:
            first_tail, second_tail = tails[0], tails[1]
            first_values = {str(row.get("规格描述") or "") for row in rows_by_tail.get(first_tail, [])}
            second_values = {str(row.get("规格描述") or "") for row in rows_by_tail.get(second_tail, [])}
            # 对比题只要求展示差异规格，避免把两侧完全一致的规格误判为缺失。
            summary_values = sorted((first_values ^ second_values) - {""})
            # 对比链路前端以“左侧订单/右侧订单”展示，不要求存在泛化的“订单号”列。
            bom_table_columns = ["材料类别", "左侧订单", "左侧规格", "右侧订单", "右侧规格"]
    return {
        "expected_status": "answerable",
        "answer_type": "table",
        "orders": tails,
        "material_categories": categories,
        "table": {"columns": bom_table_columns, "rows": matched_rows},
        "summary_values": summary_values,
    }


def build_expected_answers(ledger: dict, *, hist_zip: Path, sys_zip: Path, bom_zip: Path, prefer_db: str) -> tuple[dict, dict]:
    """构建全量标准答案。

    参数：
        ledger: 样例题台账；
        hist_zip/sys_zip/bom_zip: 用户提供源数据 zip，仅做核验和差异说明；
        prefer_db: 当前验收口径，默认 logistics_ai。
    返回值：
        标准答案和构建报告。
    """
    source_audit = {
        "prefer_source": prefer_db,
        "zip_sources": {
            "history_logistics_zip": _zip_audit(hist_zip),
            "system_2026_logistics_zip": _zip_audit(sys_zip),
            "bom_source_zip": _zip_audit(bom_zip),
        },
        "logistics_ai_db": _db_audit(),
        "source_rule": "物流标准答案优先使用 logistics_ai 中间库；源 zip 只做字段、文件数量和时间范围核验，不混用。",
    }
    db_available = bool(source_audit["logistics_ai_db"].get("available"))
    materials = _load_bom_materials()
    answers: list[dict[str, Any]] = []
    status_counter: defaultdict[str, int] = defaultdict(int)
    db = SessionLocal() if db_available else None
    try:
        for item in ledger.get("items", []):
            domain = item.get("domain")
            question = item.get("question", "")
            expected: dict[str, Any]
            if domain == "plan_bom":
                expected = _build_bom_expected(item, materials)
            elif domain == "logistics" and db is not None:
                if "为什么可能不一致" in question and any(word in question for word in ("客户名", "项目")):
                    expected = _clarification_expected(
                        "这是字段口径解释题，需要先确认按客户名称、项目名称，还是归一后的客户口径查询；系统不能把两个不同字段表达直接混为同一个统计条件。",
                        ["客户字段口径", "项目字段口径", "客户归一规则"],
                    )
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                years = extract_years(question)
                months = extract_months(question)
                if (
                    "产生原因包含" in question
                    and any(word in question for word in ("额外费用", "异常费", "异常费用"))
                ):
                    expected = _unsupported_expected(
                        "当前系统尚未固化产生原因、额外费用金额、承运商和客户之间的可追溯归因口径，不能直接按原因拆分费用明细。"
                    )
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                if _is_complex_report_question(question):
                    expected = _clarification_expected(
                        "该问题属于宽表、透视表、同比变化或多指标经营汇总类报表，需要先确认报表模板、维度范围和指标口径。",
                        ["报表模板", "多指标口径", "维度范围"],
                    )
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                if _is_2026_special_scope_mw_without_months(question, years, months):
                    expected = _clarification_expected(
                        "2026 系统侧特殊业务范围的发运量需要先确认具体月份或明确是否按截至目前累计口径统计。",
                        ["2026统计月份", "累计口径"],
                    )
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                if max(years or [0]) >= 2026 and "任务状态" in question:
                    expected = _clarification_expected(
                        "任务状态分布需要先确认状态字段来源和状态口径，例如派车状态、送货单解析状态还是主任务业务状态。",
                        ["任务状态字段", "状态口径"],
                    )
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                if not years and _should_default_to_history_years(question):
                    years = [2023, 2024, 2025]
                if not years and "项目名称" in question and any(word in question for word in ("总运量", "运量", "发运量")):
                    expected = _unsupported_expected("项目名称尚未作为标准化、可复用统计维度管理，不能直接按项目名称可靠汇总运量。")
                    status_counter[str(expected.get("expected_status") or "unknown")] += 1
                    answers.append(
                        {
                            "id": item.get("id"),
                            "original_number": item.get("original_number"),
                            "question": question,
                            "domain": domain,
                            "question_type": item.get("question_type"),
                            "expected": expected,
                        }
                    )
                    continue
                if not years:
                    expected = {
                        "expected_status": "needs_clarification",
                        "answer_type": "clarification",
                        "reason": "缺少年份，无法按正式数据范围计算。",
                        "missing_slots": ["年份"],
                    }
                elif max(years) >= 2026:
                    expected = _build_sys_expected(db, item, years, months)
                else:
                    expected = _build_hist_expected(db, item, years, months)
            elif domain == "logistics":
                expected = {
                    "expected_status": "not_evaluable",
                    "answer_type": "blocked",
                    "reason": "当前环境无法连接 logistics_ai 中间库，不能构造可信物流标准答案。",
                }
            else:
                expected = {
                    "expected_status": "needs_clarification",
                    "answer_type": "clarification",
                    "reason": "题目业务域未识别，需要先确认是物流还是计划 BOM。",
                    "missing_slots": ["业务域"],
                }
            status_counter[expected.get("expected_status", "unknown")] += 1
            answers.append(
                {
                    "id": item.get("id"),
                    "original_number": item.get("original_number"),
                    "question": question,
                    "domain": domain,
                    "question_type": item.get("question_type"),
                    "expected": expected,
                }
            )
    finally:
        if db is not None:
            db.close()

    payload = {
        "generated_at": now_iso(),
        "ledger_path": str(LEDGER_PATH),
        "total_cases": len(answers),
        "status_distribution": dict(status_counter),
        "source_audit": source_audit,
        "answers": answers,
    }
    report = {
        "generated_at": payload["generated_at"],
        "total_cases": len(answers),
        "status_distribution": dict(status_counter),
        "source_audit": source_audit,
        "bom_standardized_material_rows": len(materials),
    }
    return payload, report


def write_expected_doc(report: dict) -> None:
    """输出标准答案构建方法文档。"""
    db_audit = report.get("source_audit", {}).get("logistics_ai_db", {})
    zip_sources = report.get("source_audit", {}).get("zip_sources", {})
    lines = [
        "## 核算口径",
        "- 物流题标准答案优先使用 `logistics_ai` 中间库表时间和数据。",
        "- 23-25 年历史物流题读取 `dwd_logistics_hist_shipment_detail`。",
        "- 2026 年系统物流题读取 `dwd_logistics_ship_task`、`dwd_logistics_ship_product` 等中间库表。",
        "- 源数据 zip 用于文件数量、字段和时间范围核验；若与中间库不一致，报告差异，不混用结果。",
        "- BOM 题读取 `tmp/plan_bom/plan_bom_standardized_materials.json` 中的真实标准化材料行。",
        "",
        "## 构建结果",
        f"- 样例题数量：{report.get('total_cases')}",
        f"- 标准答案状态分布：`{report.get('status_distribution')}`",
        f"- BOM 标准化材料行数：{report.get('bom_standardized_material_rows')}",
        f"- logistics_ai 可用：{db_audit.get('available')}",
        "",
        "## 源文件核验",
    ]
    for name, audit in zip_sources.items():
        lines.append(f"- {name}: `{audit.get('path')}`，exists={audit.get('exists')}，excel_count={audit.get('excel_count')}")
    if db_audit.get("ranges"):
        lines.extend(["", "## 中间库时间范围", f"- `{db_audit.get('ranges')}`"])
    lines.extend(
        [
            "",
            "## 安全边界",
            "- 本脚本不调用 QA service、不读取前端结果、不让 LLM 查数。",
            "- 业务定义不足的问题标为需要追问或无法回答，不硬算。",
        ]
    )
    write_markdown(DOCS_DIR / "TRIAL_SAMPLE_EXPECTED_ANSWER_METHOD.md", "TRIAL_SAMPLE_EXPECTED_ANSWER_METHOD", lines)


def main() -> None:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="构建样例题标准答案")
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--hist-zip", type=Path, default=DEFAULT_HIST_ZIP)
    parser.add_argument("--sys-zip", type=Path, default=DEFAULT_SYS_ZIP)
    parser.add_argument("--bom-source-zip", type=Path, default=DEFAULT_BOM_ZIP)
    parser.add_argument("--prefer-db", default="logistics_ai")
    parser.add_argument("--output", type=Path, default=EXPECTED_PATH)
    args = parser.parse_args()

    ledger = read_json(args.ledger)
    if not ledger:
        raise FileNotFoundError(f"缺少样例题台账：{args.ledger}")
    payload, report = build_expected_answers(
        ledger,
        hist_zip=args.hist_zip,
        sys_zip=args.sys_zip,
        bom_zip=args.bom_source_zip,
        prefer_db=args.prefer_db,
    )
    write_json(args.output, payload)
    write_json(EXPECTED_REPORT_PATH, report)
    write_expected_doc(report)
    print(f"expected_answers written: {args.output}")
    print(f"total_cases={payload['total_cases']} status_distribution={payload['status_distribution']}")


if __name__ == "__main__":
    main()
