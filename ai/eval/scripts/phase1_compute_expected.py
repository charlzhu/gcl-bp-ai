#!/usr/bin/env python3
"""E2E QA Phase 1 标准答案计算脚本。

本脚本只读取 Phase 0 已解压的 Excel/xls 数据资产和样例题清单，
只向 ai/eval/expected_answers 写入可复跑产物。脚本不会调用 LLM，
不会修改业务代码，不会写数据库；2026 MySQL 类问题在缺少显式只读
配置时统一标记 blocked。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_REGIONS = ["华东", "华南", "华中", "华北", "西南", "西北", "东北"]
SUPPORTED_BOM_MATERIALS = ["玻璃", "间隙贴膜", "焊带", "汇流条", "接线盒"]
LOGISTICS_SOURCE = "logistics_history_excel"
BOM_SOURCE = "bom_xls"
MYSQL_SOURCE = "mysql_2026"


def repo_root_from_script() -> Path:
    """返回仓库根目录。

    参数：无。
    返回值：当前脚本向上回溯得到的仓库根目录 Path。
    """

    return Path(__file__).resolve().parents[3]


def clean_text(value: Any) -> str:
    """清洗单元格或问题文本。

    参数：
        value：任意原始值，常见来源是 pandas 单元格或 JSON 字段。
    返回值：去掉空值、全角空格、零宽字符和多余空白后的字符串。
    """

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    text = text.replace("\u3000", " ").replace("\u200b", "").replace("\ufeff", "")
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def compact_key(value: Any) -> str:
    """生成适合匹配的紧凑文本键。

    参数：
        value：原始文本。
    返回值：去除空白、常见分隔符并转大写后的文本键。
    """

    text = clean_text(value).upper()
    return re.sub(r"[\s_\-（）()，,。/\\]+", "", text)


def normalize_spec(value: Any) -> str:
    """标准化物流规格文本。

    参数：
        value：规格原文。
    返回值：去除隐藏字符和空白后的大写规格，用于等值匹配。
    """

    text = clean_text(value).upper()
    return re.sub(r"[\s\u200b\ufeff]+", "", text)


def normalize_location(value: Any) -> str:
    """标准化省份、城市、区域或始发地文本。

    参数：
        value：地理维度原文。
    返回值：去掉行政区后缀和空白后的文本。
    """

    text = clean_text(value)
    for suffix in ["维吾尔自治区", "壮族自治区", "回族自治区", "自治区", "特别行政区", "省", "市"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def to_number(value: Any) -> float:
    """将 Excel 数值或带单位文本转为浮点数。

    参数：
        value：原始数值、字符串或空值。
    返回值：可计算的 float；无法解析时返回 0.0。
    """

    if value is None:
        return 0.0
    try:
        if pd.isna(value):
            return 0.0
    except (TypeError, ValueError):
        pass
    if isinstance(value, (int, float)):
        return float(value)
    text = clean_text(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 0.0
    return float(match.group(0))


def json_safe(value: Any) -> Any:
    """把 pandas/numpy 类型转换为 JSON 可序列化对象。

    参数：
        value：任意待写入 JSON 的对象。
    返回值：递归转换后的 Python 基础类型。
    """

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, str)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def round_value(value: float, digits: int = 4) -> float | int:
    """按业务展示需要压缩数值精度。

    参数：
        value：待处理数值。
        digits：小数位数。
    返回值：整数型数值保持 int，其余按指定小数位四舍五入。
    """

    if abs(value - round(value)) < 1e-9:
        return int(round(value))
    return round(float(value), digits)


def read_questions(path: Path) -> list[dict[str, Any]]:
    """读取样例题 JSONL。

    参数：
        path：sample_questions.jsonl 路径。
    返回值：按文件顺序返回的问题对象列表。
    """

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def find_column(columns: list[str], candidates: list[str]) -> str | None:
    """在 Excel 字段中按关键词寻找目标列。

    参数：
        columns：原始字段名列表。
        candidates：候选关键词列表。
    返回值：匹配到的原始字段名；没有匹配时返回 None。
    """

    cleaned = [(column, clean_text(column).replace("\n", "")) for column in columns]
    for candidate in candidates:
        for original, text in cleaned:
            if candidate == text:
                return original
    for candidate in candidates:
        for original, text in cleaned:
            if candidate in text:
                return original
    return None


def infer_year_from_filename(path: Path) -> int | None:
    """从文件名推断年份。

    参数：
        path：Excel 文件路径。
    返回值：四位年份；无法识别时返回 None。
    """

    match = re.search(r"(20\d{2})", path.name)
    if match:
        return int(match.group(1))
    return None


def normalize_transport_mode(value: Any) -> str:
    """标准化运输方式。

    参数：
        value：运输方式原文。
    返回值：统一后的运输方式，汽运归为公路，铁运归为铁路。
    """

    text = clean_text(value)
    if text in {"汽运", "公路运输", "汽车"}:
        return "公路"
    if text in {"铁运", "铁路运输"}:
        return "铁路"
    return text


def load_logistics_history(logistics_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """加载并标准化 2023-2025 历史物流 Excel。

    参数：
        logistics_dir：Phase 0 解压出的历史物流目录。
    返回值：标准化 DataFrame，以及文件/sheet 画像字典。
    """

    column_map = {
        "date": ["发货日期", "发运日期"],
        "customer": ["客户名称（标准名称；最终客户）", "客户名称"],
        "contract_no": ["合同编号"],
        "procurement_no": ["询比价编号"],
        "address": ["地址"],
        "province": ["省份", "省"],
        "city": ["城市", "市"],
        "distance_km": ["路程/KM", "路程"],
        "product_spec": ["规格"],
        "power": ["功率"],
        "planned_count": ["日计划发运件数", "计划发运件数"],
        "shipment_count": ["日实际发运件数", "实际发运件数"],
        "shipment_watt": ["日实际发运瓦数", "实际发运瓦数"],
        "achieve_rate": ["发运达标率"],
        "vehicle_model": ["要求中标车辆型号"],
        "pallet_per_vehicle": ["每车装在托数", "每车装载托数"],
        "vehicle_count": ["车辆数", "车次"],
        "carrier": ["物流公司"],
        "unit_price_vehicle": ["单价/车"],
        "total_fee": ["总费用(元)", "总费用"],
        "yuan_per_watt": ["元/瓦"],
        "extra_fee": ["额外费用", "异常费"],
        "reason": ["产生原因"],
        "remark": ["备注（倒运，中转等特殊情况）", "备注"],
        "transport_mode": ["运输方式"],
        "region": ["区域"],
        "month_name": ["月度"],
        "origin": ["始发地"],
    }
    frames: list[pd.DataFrame] = []
    profile: dict[str, Any] = {"files": []}
    for file_path in sorted(logistics_dir.glob("*.xlsx")):
        xl = pd.ExcelFile(file_path)
        file_info = {"file": str(file_path), "sheets": []}
        for sheet_name in xl.sheet_names:
            raw = pd.read_excel(file_path, sheet_name=sheet_name, dtype=object)
            raw = raw.dropna(how="all")
            if raw.empty:
                file_info["sheets"].append({"sheet": sheet_name, "rows": 0, "used": False})
                continue
            selected: dict[str, Any] = {}
            for target, candidates in column_map.items():
                source_column = find_column(list(raw.columns), candidates)
                if source_column is None:
                    selected[target] = ""
                else:
                    selected[target] = raw[source_column]
            frame = pd.DataFrame(selected)
            frame["source"] = LOGISTICS_SOURCE
            frame["file"] = str(file_path)
            frame["file_name"] = file_path.name
            frame["sheet"] = sheet_name
            frame["excel_row"] = raw.index.astype(int) + 2
            inferred_year = infer_year_from_filename(file_path)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["year"] = frame["date"].dt.year.fillna(inferred_year).astype("Int64")
            frame["month"] = frame["date"].dt.month.astype("Int64")
            month_from_name = frame["month_name"].map(lambda value: to_number(value) or None)
            frame["month"] = frame["month"].fillna(month_from_name).astype("Int64")
            frame["quarter"] = frame["month"].map(lambda month: f"Q{int((month - 1) // 3 + 1)}" if pd.notna(month) else "")
            frame["year_month"] = [
                f"{int(year):04d}-{int(month):02d}" if pd.notna(year) and pd.notna(month) else ""
                for year, month in zip(frame["year"], frame["month"], strict=False)
            ]
            for text_col in [
                "customer",
                "contract_no",
                "procurement_no",
                "address",
                "province",
                "city",
                "product_spec",
                "vehicle_model",
                "carrier",
                "reason",
                "remark",
                "transport_mode",
                "region",
                "origin",
            ]:
                frame[text_col] = frame[text_col].map(clean_text)
            frame["province_norm"] = frame["province"].map(normalize_location)
            frame["city_norm"] = frame["city"].map(normalize_location)
            frame["region_norm"] = frame["region"].map(clean_text)
            frame["origin_norm"] = frame["origin"].map(normalize_location)
            frame["transport_mode_std"] = frame["transport_mode"].map(normalize_transport_mode)
            frame["product_spec_norm"] = frame["product_spec"].map(normalize_spec)
            for number_col in [
                "distance_km",
                "power",
                "planned_count",
                "shipment_count",
                "shipment_watt",
                "achieve_rate",
                "pallet_per_vehicle",
                "vehicle_count",
                "unit_price_vehicle",
                "total_fee",
                "yuan_per_watt",
                "extra_fee",
            ]:
                frame[number_col] = frame[number_col].map(to_number)
            frames.append(frame)
            file_info["sheets"].append({"sheet": sheet_name, "rows": int(len(frame)), "used": True})
        profile["files"].append(file_info)
    if not frames:
        return pd.DataFrame(), profile
    return pd.concat(frames, ignore_index=True), profile


def detect_bom_header(raw: pd.DataFrame) -> int | None:
    """识别 BOM sheet 的物料表头行。

    参数：
        raw：header=None 读取的 BOM sheet。
    返回值：表头行的 DataFrame 下标；无法识别时返回 None。
    """

    for idx, row in raw.iterrows():
        values = [clean_text(value) for value in row.tolist()]
        joined = "|".join(values)
        if "SAP编码" in joined and "物料名称" in joined and "描述" in joined:
            return int(idx)
    return None


def extract_bom_meta(file_path: Path, raw: pd.DataFrame) -> dict[str, str]:
    """从 BOM 文件名和表头区域提取订单元数据。

    参数：
        file_path：BOM xls 路径。
        raw：header=None 读取的原始 sheet。
    返回值：包含订单号、短订单号、型号和版本的字典。
    """

    file_name = file_path.name
    order_match = re.search(r"(20\d{2}-\d{5})", file_name)
    model_match = re.search(r"(NT\d{2}R?\d{2}GDF|NT\d{2}R?/\d{2}GDF)", file_name, flags=re.I)
    version_match = re.search(r"Billofmaterials-([A-Z])", file_name, flags=re.I)
    meta = {
        "order_no": order_match.group(1) if order_match else "",
        "order_suffix": order_match.group(1).split("-")[-1] if order_match else "",
        "model": model_match.group(1).upper().replace("/", "") if model_match else "",
        "version": version_match.group(1).upper() if version_match else "",
        "order_name": "",
    }
    for _, row in raw.head(6).iterrows():
        values = [clean_text(value) for value in row.tolist()]
        for pos, value in enumerate(values):
            if value == "订单名称" and pos + 1 < len(values):
                meta["order_name"] = values[pos + 1]
    return meta


def load_bom_files(bom_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """加载并标准化 BOM xls 文件。

    参数：
        bom_dir：Phase 0 解压出的 BOM 文件目录。
    返回值：标准化物料行 DataFrame，以及文件画像字典。
    """

    frames: list[pd.DataFrame] = []
    profile: dict[str, Any] = {"files": []}
    for file_path in sorted(bom_dir.glob("*.xls")):
        xl = pd.ExcelFile(file_path)
        for sheet_name in xl.sheet_names:
            raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None, dtype=object)
            header_idx = detect_bom_header(raw)
            meta = extract_bom_meta(file_path, raw)
            if header_idx is None:
                profile["files"].append(
                    {"file": str(file_path), "sheet": sheet_name, "rows": 0, "header_found": False, **meta}
                )
                continue
            headers = [clean_text(value) for value in raw.iloc[header_idx].tolist()]
            data = raw.iloc[header_idx + 1 :].copy()
            data.columns = headers
            data = data.dropna(how="all")
            column_map = {
                "sap_code": find_column(list(data.columns), ["SAP编码"]),
                "material_name": find_column(list(data.columns), ["物料名称"]),
                "description": find_column(list(data.columns), ["描述"]),
                "quantity": find_column(list(data.columns), ["标准用量"]),
                "unit": find_column(list(data.columns), ["单位"]),
                "remark": find_column(list(data.columns), ["备注"]),
            }
            selected: dict[str, Any] = {}
            for target, source_col in column_map.items():
                selected[target] = data[source_col] if source_col is not None else ""
            frame = pd.DataFrame(selected)
            frame["source"] = BOM_SOURCE
            frame["file"] = str(file_path)
            frame["file_name"] = file_path.name
            frame["sheet"] = sheet_name
            frame["excel_row"] = data.index.astype(int) + 1
            for key, value in meta.items():
                frame[key] = value
            for text_col in ["sap_code", "material_name", "description", "unit", "remark"]:
                frame[text_col] = frame[text_col].map(clean_text)
            frame["quantity"] = frame["quantity"].map(lambda value: clean_text(value) or to_number(value))
            frame["material_key"] = (frame["material_name"] + " " + frame["description"]).map(clean_text)
            frame = frame[(frame["sap_code"] != "") | (frame["material_name"] != "") | (frame["description"] != "")]
            frames.append(frame)
            profile["files"].append(
                {
                    "file": str(file_path),
                    "sheet": sheet_name,
                    "rows": int(len(frame)),
                    "header_found": True,
                    **meta,
                }
            )
    if not frames:
        return pd.DataFrame(), profile
    return pd.concat(frames, ignore_index=True), profile


def extract_years(question: str, year_guess: list[int] | None = None) -> list[int]:
    """从问题中提取历史年份。

    参数：
        question：用户问题文本。
        year_guess：Phase 0 预识别年份。
    返回值：识别到的年份列表；历史类未给定年份时返回 2023-2025。
    """

    years: set[int] = set()
    for match in re.findall(r"20(23|24|25|26)", question):
        years.add(2000 + int(match))
    for match in re.findall(r"(?<!\d)(23|24|25|26)\s*年", question):
        years.add(2000 + int(match))
    for year in year_guess or []:
        if year in {2023, 2024, 2025, 2026}:
            years.add(int(year))
    if re.search(r"2023\s*(?:年)?\s*(?:至|到|-|~)\s*2025", question) or "23年至25年" in question:
        years.update({2023, 2024, 2025})
    if not years and ("历史" in question or "台账" in question or "2023-2025" in question):
        years.update({2023, 2024, 2025})
    return sorted(years)


def extract_months(question: str) -> list[int]:
    """从问题中提取月份。

    参数：
        question：用户问题文本。
    返回值：月份数字列表；未提取到时返回空列表。
    """

    months: set[int] = set()
    for match in re.findall(r"(?<!\d)(1[0-2]|0?[1-9])\s*月份?", question):
        months.add(int(match))
    for match in re.findall(r"20\d{2}[-/](1[0-2]|0[1-9])", question):
        months.add(int(match))
    return sorted(months)


def extract_quarter(question: str) -> str | None:
    """从问题中提取季度。

    参数：
        question：用户问题文本。
    返回值：Q1-Q4；无法识别时返回 None。
    """

    match = re.search(r"Q([1-4])", question, flags=re.I)
    if match:
        return f"Q{match.group(1)}"
    match = re.search(r"第([一二三四1234])季度", question)
    if not match:
        return None
    mapping = {"一": "1", "二": "2", "三": "3", "四": "4"}
    return f"Q{mapping.get(match.group(1), match.group(1))}"


def extract_region(question: str) -> str | None:
    """从问题中提取区域。

    参数：
        question：用户问题文本。
    返回值：区域名；未识别时返回 None。
    """

    for region in SUPPORTED_REGIONS:
        if region in question:
            return region
    return None


def extract_from_known(question: str, values: list[str], require_suffix: str | None = None) -> str | None:
    """从已知维度值中提取问题槽位。

    参数：
        question：用户问题文本。
        values：来自数据集的候选维度值。
        require_suffix：可选后缀，比如“城市”，用于减少误匹配。
    返回值：匹配到的维度值；未识别时返回 None。
    """

    normalized_question = normalize_location(question)
    for value in sorted({clean_text(v) for v in values if clean_text(v)}, key=len, reverse=True):
        norm = normalize_location(value)
        if not norm:
            continue
        if require_suffix and f"{norm}{require_suffix}" not in normalized_question:
            continue
        if norm in normalized_question:
            return norm
    return None


def extract_transport_mode(question: str) -> str | None:
    """从问题中提取并标准化运输方式。

    参数：
        question：用户问题文本。
    返回值：公路、铁路、水路等标准运输方式；未识别时返回 None。
    """

    if "公路" in question or "汽运" in question:
        return "公路"
    if "铁路" in question or "铁运" in question:
        return "铁路"
    if "水路" in question:
        return "水路"
    return None


def extract_product_spec(question: str) -> str | None:
    """从问题中提取物流产品规格。

    参数：
        question：用户问题文本。
    返回值：标准化规格；未识别时返回 None。
    """

    match = re.search(r"规格为([^，,。?？\s]+)", question)
    if match:
        return normalize_spec(match.group(1))
    match = re.search(r"GCL-[A-Z0-9R/]+-\d+W", question, flags=re.I)
    if match:
        return normalize_spec(match.group(0))
    return None


def make_trace(
    question_id: str,
    status: str,
    source: str,
    files: list[str] | None,
    sheets: list[str] | None,
    filters: dict[str, Any],
    fields: list[str],
    aggregation: str,
    row_count_before_filter: int,
    row_count_after_filter: int,
    calculation_steps: list[Any],
    reason: str = "",
) -> dict[str, Any]:
    """构造统一 trace 对象。

    参数：
        question_id：题目 ID。
        status：expected/no_answer/blocked/unsupported。
        source：数据来源标识。
        files：参与计算的文件路径列表。
        sheets：参与计算的 sheet 名列表。
        filters：过滤条件。
        fields：参与计算的标准字段。
        aggregation：聚合方式描述。
        row_count_before_filter：过滤前行数。
        row_count_after_filter：过滤后行数。
        calculation_steps：关键计算步骤。
        reason：非 expected 状态的原因。
    返回值：可写入 expected_answer_trace.jsonl 的字典。
    """

    return {
        "question_id": question_id,
        "status": status,
        "source": source,
        "file": files or [],
        "sheet": sheets or [],
        "filters": json_safe(filters),
        "fields": fields,
        "aggregation": aggregation,
        "row_count_before_filter": int(row_count_before_filter),
        "row_count_after_filter": int(row_count_after_filter),
        "calculation_steps": json_safe(calculation_steps),
        "reason": reason,
    }


def make_answer(
    row: dict[str, Any],
    status: str,
    category: str,
    capability: str,
    answer: Any = None,
    reason: str = "",
) -> dict[str, Any]:
    """构造统一答案对象。

    参数：
        row：样例题原始对象。
        status：expected/no_answer/blocked/unsupported。
        category：脚本识别或沿用的分类。
        capability：命中的支持能力。
        answer：标准答案数据。
        reason：非 expected 状态原因。
    返回值：可写入 expected_answers.jsonl 的字典。
    """

    return {
        "question_id": row["question_id"],
        "seq": row.get("seq"),
        "question": row["question"],
        "domain": row.get("domain_guess", ""),
        "category": category,
        "capability": capability,
        "status": status,
        "answer": json_safe(answer),
        "reason": reason,
    }


def apply_logistics_filters(
    df: pd.DataFrame,
    years: list[int] | None = None,
    months: list[int] | None = None,
    quarter: str | None = None,
    region: str | None = None,
    province: str | None = None,
    city: str | None = None,
    origin: str | None = None,
    transport_mode: str | None = None,
    product_spec: str | None = None,
    carrier: str | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """按识别出的槽位过滤历史物流数据。

    参数：
        df：标准化历史物流 DataFrame。
        years/months/quarter/region/province/city/origin/transport_mode/product_spec/carrier：
            可选过滤条件。
    返回值：过滤后的 DataFrame，以及用于 trace 的过滤条件字典。
    """

    filtered = df
    filters: dict[str, Any] = {}
    if years:
        filtered = filtered[filtered["year"].isin(years)]
        filters["year"] = years
    if months:
        filtered = filtered[filtered["month"].isin(months)]
        filters["month"] = months
    if quarter:
        filtered = filtered[filtered["quarter"] == quarter]
        filters["quarter"] = quarter
    if region:
        filtered = filtered[filtered["region_norm"] == region]
        filters["region"] = region
    if province:
        filtered = filtered[filtered["province_norm"] == province]
        filters["province"] = province
    if city:
        filtered = filtered[filtered["city_norm"] == city]
        filters["city"] = city
    if origin:
        filtered = filtered[filtered["origin_norm"] == origin]
        filters["origin"] = origin
    if transport_mode:
        filtered = filtered[filtered["transport_mode_std"] == transport_mode]
        filters["transport_mode_std"] = transport_mode
    if product_spec:
        filtered = filtered[filtered["product_spec_norm"] == product_spec]
        filters["product_spec_norm"] = product_spec
    if carrier:
        filtered = filtered[filtered["carrier"] == carrier]
        filters["carrier"] = carrier
    return filtered, filters


def source_files_and_sheets(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """从过滤结果中提取文件和 sheet。

    参数：
        df：过滤后的 DataFrame。
    返回值：文件路径列表和 sheet 名列表。
    """

    if df.empty:
        return [], []
    return sorted(df["file"].dropna().unique().tolist()), sorted(df["sheet"].dropna().unique().tolist())


def aggregate_scalar(
    row: dict[str, Any],
    df: pd.DataFrame,
    filtered: pd.DataFrame,
    filters: dict[str, Any],
    value_field: str,
    aggregation: str,
    capability: str,
    digits: int = 4,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """聚合单个数值答案。

    参数：
        row：样例题原始对象。
        df：完整历史物流 DataFrame。
        filtered：过滤后的 DataFrame。
        filters：trace 过滤条件。
        value_field：求和或计数字段。
        aggregation：聚合方式描述。
        capability：支持能力名。
        digits：小数位。
    返回值：答案对象和 trace 对象。
    """

    if aggregation == "count_rows":
        value = int(len(filtered))
    else:
        value = round_value(float(filtered[value_field].sum()), digits)
    files, sheets = source_files_and_sheets(filtered)
    answer = {
        "value": value,
        "unit": {
            "shipment_count": "件",
            "shipment_watt": "瓦",
            "total_fee": "元",
            "vehicle_count": "车次",
            "count_rows": "条",
        }.get(value_field, ""),
        "filters": filters,
    }
    trace = make_trace(
        row["question_id"],
        "expected",
        LOGISTICS_SOURCE,
        files,
        sheets,
        filters,
        [value_field],
        aggregation,
        len(df),
        len(filtered),
        [
            {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
            {"step": aggregation, "field": value_field, "value": value},
        ],
    )
    return make_answer(row, "expected", row.get("category_guess", ""), capability, answer), trace


def handle_monthly_fee(
    row: dict[str, Any],
    df: pd.DataFrame,
    known: dict[str, list[str]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """处理各月/月度物流总费用问题。

    参数：
        row：样例题原始对象。
        df：完整历史物流 DataFrame。
        known：省市、始发地、物流公司等已知维度值。
    返回值：命中时返回答案和 trace；未命中时返回 None。
    """

    question = row["question"]
    if not re.search(r"总运费|总费用|运费", question):
        return None
    if re.search(r"额外费用|异常费用|占比|同比|变化率|变化额", question):
        return None
    is_monthly_group = bool(re.search(r"每个月|各月|按月份|按月|月份", question))
    years = [year for year in extract_years(question, row.get("year_guess")) if year in {2023, 2024, 2025}]
    months = extract_months(question)
    if not is_monthly_group and not (years and months):
        return None
    if not years:
        years = [2023, 2024, 2025]
    region = extract_region(question)
    province = extract_from_known(question, known["provinces"])
    city = extract_from_known(question, known["cities"])
    origin = extract_from_known(question, known["origins"])
    carrier = extract_from_known(question, known["carriers"])
    filtered, filters = apply_logistics_filters(
        df,
        years=years,
        months=months or None,
        region=region,
        province=province,
        city=city,
        origin=origin,
        carrier=carrier,
    )
    files, sheets = source_files_and_sheets(filtered)
    if months and not is_monthly_group:
        return aggregate_scalar(
            row,
            df,
            filtered,
            filters,
            "total_fee",
            "sum",
            "logistics_month_total_fee",
            digits=2,
        )
    group_cols = ["year", "month"]
    if "各区域" in question or "区域×月份" in question:
        group_cols.append("region_norm")
    grouped = (
        filtered.groupby(group_cols, dropna=False)["total_fee"]
        .sum()
        .reset_index()
        .sort_values(group_cols)
    )
    rows = []
    for item in grouped.to_dict(orient="records"):
        output = {
            "year": int(item["year"]) if pd.notna(item["year"]) else None,
            "month": int(item["month"]) if pd.notna(item["month"]) else None,
            "total_fee": round_value(float(item["total_fee"]), 2),
        }
        if "region_norm" in item:
            output["region"] = item["region_norm"]
        rows.append(output)
    answer = {"rows": rows, "unit": "元", "filters": filters}
    trace = make_trace(
        row["question_id"],
        "expected",
        LOGISTICS_SOURCE,
        files,
        sheets,
        filters,
        ["year", "month", "total_fee"],
        f"group_by({','.join(group_cols)}).sum(total_fee)",
        len(df),
        len(filtered),
        [
            {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
            {"step": "group_sum", "group_by": group_cols, "row_count": len(rows)},
        ],
    )
    return make_answer(row, "expected", row.get("category_guess", ""), "logistics_month_total_fee", answer), trace


def is_complex_logistics_report_question(question: str) -> bool:
    """判断题目是否属于当前 data-qa 边界外的复杂物流报表。

    参数：question 为样例题原文。
    返回值：需要报表模板/多维度/多指标口径确认则返回 True。
    业务逻辑：Phase 1 标准答案不能把复杂报表降级成单一标量答案，否则会把产品侧合理追问误判为失败。
    """

    compact = re.sub(r"\s+", "", question or "")
    complex_keywords = (
        "宽表",
        "矩阵",
        "同一张明细汇总表",
        "季度经营汇总表",
        "跨年对比表",
        "年度对比表",
        "车型结构表",
        "城市明细排行榜",
        "按城市汇总",
        "按月份拆分",
        "月度汇总表",
        "同一合同编号对应多个目的城市",
        "发往各省份",
        "备注中包含",
        "热力表",
        "交叉表",
        "明细加汇总",
        "按目的省份和车型组合",
        "费用占比",
        "前20条发运记录",
        "前20物流公司",
    )
    if any(keyword in compact for keyword in complex_keywords):
        return True
    if "不同车型" in compact and "始发" not in compact:
        # “物流公司 + 不同车型 + 多指标”当前没有稳定的承运商车型报表模板；
        # 只放行 planner 已确认的“年份 + 始发地 + 不同车型”题型，避免把公司车型报表误算成全局车次。
        return True
    if (
        any(keyword in compact for keyword in ("发运量", "运量", "发运瓦数"))
        and any(keyword in compact for keyword in ("总费用", "总运费", "运输费用"))
        and any(keyword in compact for keyword in ("按月份", "月份汇总", "月度汇总"))
        and any(keyword in compact for keyword in ("区分2023", "三个年度", "分别展示2023", "2023、2024、2025"))
    ):
        return True
    return False


def handle_logistics(row: dict[str, Any], df: pd.DataFrame, known: dict[str, list[str]]) -> tuple[dict[str, Any], dict[str, Any]]:
    """处理历史物流标准答案。

    参数：
        row：样例题原始对象。
        df：标准化历史物流 DataFrame。
        known：已知维度候选值。
    返回值：答案对象和 trace 对象。
    """

    question = row["question"]
    question_id = row["question_id"]
    category = row.get("category_guess", "")
    years_all = extract_years(question, row.get("year_guess"))
    if 2026 in years_all or row.get("needs_db_2026_guess"):
        reason = db_blocked_reason()
        trace = make_trace(
            question_id,
            "blocked",
            MYSQL_SOURCE,
            [],
            [],
            {"year": [year for year in years_all if year == 2026] or [2026]},
            [],
            "blocked_before_db_access",
            0,
            0,
            [{"step": "db_access_check", "result": "blocked", "reason": reason}],
            reason,
        )
        return make_answer(row, "blocked", category, "mysql_2026_readonly_blocked", None, reason), trace
    if is_complex_logistics_report_question(question):
        # 复杂报表题需要表格模板、维度列和多指标口径共同确认；
        # 当前产品侧会追问而不是用单一聚合值冒充完整答案，标准答案侧也必须标记为 unsupported。
        return unsupported(row, "复杂宽表/矩阵/排行榜/结构表/年度对比表超出当前物流 data-qa 稳定可执行边界。")
    monthly = handle_monthly_fee(row, df, known)
    if monthly is not None:
        return monthly

    years = [year for year in years_all if year in {2023, 2024, 2025}]
    if not years:
        years = [2023, 2024, 2025]
    region = extract_region(question)
    province = extract_from_known(question, known["provinces"])
    city = extract_from_known(question, known["cities"], require_suffix="城市")
    origin = extract_from_known(question, known["origins"])
    transport_mode = extract_transport_mode(question)
    quarter = extract_quarter(question)
    months = extract_months(question)

    if category == "logistics_count" and re.search(r"发运件数|总件数|发运的总件数", question):
        filtered, filters = apply_logistics_filters(
            df,
            years=years,
            months=months or None,
            region=region,
            province=province,
            transport_mode=transport_mode,
        )
        return aggregate_scalar(row, df, filtered, filters, "shipment_count", "sum", "logistics_total_shipment_count")

    if category == "logistics_total_fee" and re.search(r"总费用|总运费|运费", question):
        if re.search(r"额外费用|异常费用|占比|比例|同比|变化率|变化额|透视|矩阵", question):
            return unsupported(row, "该费用题包含占比/同比/矩阵/额外费用等 Phase 1 未纳入的派生分析。")
        filtered, filters = apply_logistics_filters(
            df,
            years=years,
            months=months or None,
            region=region,
            province=province,
            transport_mode=transport_mode,
        )
        return aggregate_scalar(row, df, filtered, filters, "total_fee", "sum", "logistics_total_fee", digits=2)

    if category == "logistics_transport_mode_count" and re.search(r"记录数|多少条|运输方式", question):
        if transport_mode is None:
            return no_answer(row, LOGISTICS_SOURCE, "无法从问题中识别运输方式槽位。")
        filtered, filters = apply_logistics_filters(df, years=years, transport_mode=transport_mode)
        return aggregate_scalar(row, df, filtered, filters, "count_rows", "count_rows", "logistics_transport_mode_record_count")

    if category == "logistics_shipment_watt" and "规格" in question and re.search(r"总瓦数|发运总瓦数", question):
        product_spec = extract_product_spec(question)
        if not product_spec:
            return no_answer(row, LOGISTICS_SOURCE, "无法识别规格槽位。")
        filtered, filters = apply_logistics_filters(df, years=years, product_spec=product_spec)
        return aggregate_scalar(row, df, filtered, filters, "shipment_watt", "sum", "logistics_spec_total_watt")

    if category == "logistics_vehicle_count" and (quarter or re.search(r"总车次|车辆数|车次", question)):
        filtered, filters = apply_logistics_filters(
            df,
            years=years,
            quarter=quarter,
            region=region,
            province=province,
            origin=origin,
            months=months or None,
        )
        return aggregate_scalar(row, df, filtered, filters, "vehicle_count", "sum", "logistics_vehicle_count")

    if category == "logistics_cost_sort" and "各运输方式" in question and region:
        filtered, filters = apply_logistics_filters(df, years=years, region=region)
        grouped = (
            filtered.groupby("transport_mode_std", dropna=False)
            .agg(total_fee=("total_fee", "sum"), shipment_watt=("shipment_watt", "sum"), row_count=("transport_mode_std", "size"))
            .reset_index()
        )
        grouped = grouped[grouped["transport_mode_std"] != ""]
        grouped["avg_yuan_per_watt"] = grouped.apply(
            lambda item: float(item["total_fee"]) / float(item["shipment_watt"]) if item["shipment_watt"] else 0.0,
            axis=1,
        )
        grouped = grouped.sort_values(["avg_yuan_per_watt", "transport_mode_std"])
        rows = [
            {
                "transport_mode": item["transport_mode_std"],
                "avg_yuan_per_watt": round_value(float(item["avg_yuan_per_watt"]), 6),
                "total_fee": round_value(float(item["total_fee"]), 2),
                "shipment_watt": round_value(float(item["shipment_watt"]), 0),
                "row_count": int(item["row_count"]),
            }
            for item in grouped.to_dict(orient="records")
        ]
        files, sheets = source_files_and_sheets(filtered)
        trace = make_trace(
            question_id,
            "expected",
            LOGISTICS_SOURCE,
            files,
            sheets,
            filters,
            ["transport_mode_std", "total_fee", "shipment_watt"],
            "group_by(transport_mode_std).sum(total_fee)/sum(shipment_watt).sort_asc",
            len(df),
            len(filtered),
            [
                {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
                {"step": "weighted_average", "formula": "sum(total_fee)/sum(shipment_watt)", "groups": len(rows)},
            ],
        )
        return make_answer(row, "expected", category, "logistics_region_transport_avg_yuan_per_watt_sort", {"rows": rows}, ""), trace

    if category == "logistics_loading_efficiency" and origin and months and years:
        filtered, filters = apply_logistics_filters(df, years=years, months=months, origin=origin)
        value = 0.0
        if filtered["vehicle_count"].sum():
            value = float((filtered["pallet_per_vehicle"] * filtered["vehicle_count"]).sum()) / float(filtered["vehicle_count"].sum())
        answer = {
            "value": round_value(value, 4),
            "unit": "托/车",
            "filters": filters,
        }
        files, sheets = source_files_and_sheets(filtered)
        trace = make_trace(
            question_id,
            "expected",
            LOGISTICS_SOURCE,
            files,
            sheets,
            filters,
            ["pallet_per_vehicle", "vehicle_count"],
            "sum(pallet_per_vehicle*vehicle_count)/sum(vehicle_count)",
            len(df),
            len(filtered),
            [
                {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
                {
                    "step": "weighted_average",
                    "numerator": round_value(float((filtered["pallet_per_vehicle"] * filtered["vehicle_count"]).sum()), 4),
                    "denominator": round_value(float(filtered["vehicle_count"].sum()), 4),
                    "value": round_value(value, 4),
                },
            ],
        )
        return make_answer(row, "expected", category, "logistics_origin_month_avg_pallet_per_vehicle", answer), trace

    if category == "logistics_topn" and province and "客户" in question and re.search(r"前\s*5|前五", question):
        filtered, filters = apply_logistics_filters(df, years=years, province=province)
        grouped = (
            filtered.groupby("customer", dropna=False)
            .agg(total_fee=("total_fee", "sum"), shipment_watt=("shipment_watt", "sum"), row_count=("customer", "size"))
            .reset_index()
            .sort_values(["total_fee", "shipment_watt"], ascending=[False, False])
            .head(5)
        )
        rows = [
            {
                "customer": item["customer"],
                "total_fee": round_value(float(item["total_fee"]), 2),
                "shipment_watt": round_value(float(item["shipment_watt"]), 0),
                "row_count": int(item["row_count"]),
            }
            for item in grouped.to_dict(orient="records")
        ]
        files, sheets = source_files_and_sheets(filtered)
        trace = make_trace(
            question_id,
            "expected",
            LOGISTICS_SOURCE,
            files,
            sheets,
            filters,
            ["customer", "total_fee", "shipment_watt"],
            "group_by(customer).sum(total_fee,shipment_watt).top5_by_total_fee",
            len(df),
            len(filtered),
            [
                {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
                {"step": "group_topn", "group_by": "customer", "top_n": 5, "rows": len(rows)},
            ],
        )
        return make_answer(row, "expected", category, "logistics_province_customer_top5_fee_watt", {"rows": rows}), trace

    if category == "logistics_company_unit_price" and city and "物流公司" in question and "平均单价/车" in question:
        filtered, filters = apply_logistics_filters(df, years=years, city=city)
        grouped = (
            filtered.groupby("carrier", dropna=False)
            .agg(total_fee=("total_fee", "sum"), vehicle_count=("vehicle_count", "sum"), row_count=("carrier", "size"))
            .reset_index()
        )
        grouped = grouped[grouped["carrier"] != ""]
        grouped["avg_unit_price_per_vehicle"] = grouped.apply(
            lambda item: float(item["total_fee"]) / float(item["vehicle_count"]) if item["vehicle_count"] else 0.0,
            axis=1,
        )
        grouped = grouped.sort_values(["avg_unit_price_per_vehicle", "carrier"])
        rows = [
            {
                "carrier": item["carrier"],
                "avg_unit_price_per_vehicle": round_value(float(item["avg_unit_price_per_vehicle"]), 2),
                "total_fee": round_value(float(item["total_fee"]), 2),
                "vehicle_count": round_value(float(item["vehicle_count"]), 0),
                "row_count": int(item["row_count"]),
            }
            for item in grouped.to_dict(orient="records")
        ]
        files, sheets = source_files_and_sheets(filtered)
        trace = make_trace(
            question_id,
            "expected",
            LOGISTICS_SOURCE,
            files,
            sheets,
            filters,
            ["carrier", "total_fee", "vehicle_count"],
            "group_by(carrier).sum(total_fee)/sum(vehicle_count)",
            len(df),
            len(filtered),
            [
                {"step": "filter", "filters": filters, "matched_rows": int(len(filtered))},
                {"step": "weighted_average", "formula": "sum(total_fee)/sum(vehicle_count)", "groups": len(rows)},
            ],
        )
        return make_answer(row, "expected", category, "logistics_city_carrier_avg_unit_price_per_vehicle", {"rows": rows}), trace

    return unsupported(row, f"Phase 1 未纳入该历史物流题型：{category}")


def material_aliases(material: str) -> list[str]:
    """返回 BOM 关键物料的匹配别名。

    参数：
        material：标准物料名。
    返回值：用于物料名称/描述匹配的别名列表。
    """

    aliases = {
        "玻璃": ["光伏玻璃", "玻璃"],
        "间隙贴膜": ["间隙贴膜", "间隙膜"],
        "焊带": ["焊带", "互联条"],
        "汇流条": ["汇流条"],
        "接线盒": ["接线盒", "线盒"],
    }
    return aliases.get(material, [material])


def extract_bom_materials(question: str) -> list[str]:
    """从 BOM 问题中提取需要查询的关键物料。

    参数：
        question：用户问题文本。
    返回值：标准物料名列表；未提取时返回默认五类关键物料。
    """

    materials = []
    for material in SUPPORTED_BOM_MATERIALS:
        if material in question or (material == "接线盒" and "线盒" in question) or (material == "间隙贴膜" and "间隙膜" in question):
            materials.append(material)
    return materials or SUPPORTED_BOM_MATERIALS.copy()


def extract_bom_order_suffixes(question: str) -> list[str]:
    """从 BOM 问题中提取订单短号。

    参数：
        question：用户问题文本。
    返回值：五位订单短号列表。
    """

    suffixes: list[str] = []
    for full in re.findall(r"20\d{2}-(\d{5})", question):
        suffixes.append(full)
    for suffix in re.findall(r"订单(?:[A-Z]-)?0*(\d{1,5})", question, flags=re.I):
        suffixes.append(suffix.zfill(5))
    for suffix in re.findall(r"(?<!\d)(0\d{4})(?!\d)", question):
        suffixes.append(suffix)
    seen: set[str] = set()
    ordered: list[str] = []
    for suffix in suffixes:
        if suffix not in seen:
            seen.add(suffix)
            ordered.append(suffix)
    return ordered


def extract_bom_models(question: str) -> list[str]:
    """从 BOM 问题中提取组件型号。

    参数：
        question：用户问题文本。
    返回值：去除斜杠后的型号列表。
    """

    models = []
    for match in re.findall(r"NT\d{2}R?/?\d{2}GDF", question, flags=re.I):
        models.append(match.upper().replace("/", ""))
    return list(dict.fromkeys(models))


def select_bom_files(question: str, bom_df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """根据订单号和型号选择 BOM 文件。

    参数：
        question：用户问题文本。
        bom_df：标准化 BOM DataFrame。
    返回值：匹配文件对应的 BOM 行，以及 trace 过滤条件。
    """

    suffixes = extract_bom_order_suffixes(question)
    models = extract_bom_models(question)
    selected = bom_df
    filters: dict[str, Any] = {}
    if suffixes:
        selected = selected[selected["order_suffix"].isin(suffixes)]
        filters["order_suffix"] = suffixes
    if models:
        model_filtered = selected[selected["model"].isin(models)]
        if not model_filtered.empty:
            selected = model_filtered
            filters["model"] = models
    if not suffixes and not models:
        # “现有订单”没有给出可执行的订单/型号范围，网页应追问；标准答案不能把全量 BOM 当作用户意图。
        filters["order_suffix"] = []
        filters["ambiguous_reason"] = "missing_order_or_model_scope"
        return selected.iloc[0:0], filters
    return selected, filters


def filter_bom_material_rows(selected: pd.DataFrame, materials: list[str]) -> pd.DataFrame:
    """从已选 BOM 文件中过滤关键物料行。

    参数：
        selected：已按订单/型号选择的 BOM 行。
        materials：标准关键物料列表。
    返回值：带标准 material 字段的匹配物料行。
    """

    parts: list[pd.DataFrame] = []
    for material in materials:
        aliases = material_aliases(material)
        mask = selected["material_key"].map(lambda value: any(alias in value for alias in aliases))
        matched = selected[mask].copy()
        matched["material"] = material
        parts.append(matched)
    if not parts:
        return selected.iloc[0:0].copy()
    return pd.concat(parts, ignore_index=True).drop_duplicates(
        subset=["file", "sheet", "excel_row", "material"], keep="first"
    )


def bom_rows_to_records(rows: pd.DataFrame) -> list[dict[str, Any]]:
    """将 BOM 物料行转换为答案记录。

    参数：
        rows：过滤后的 BOM DataFrame。
    返回值：包含文件、sheet、订单、物料和描述的记录列表。
    """

    records = []
    sort_cols = ["order_suffix", "version", "material", "file_name", "excel_row"]
    for item in rows.sort_values(sort_cols).to_dict(orient="records"):
        records.append(
            {
                "order_no": item.get("order_no", ""),
                "order_suffix": item.get("order_suffix", ""),
                "model": item.get("model", ""),
                "version": item.get("version", ""),
                "file": item.get("file", ""),
                "sheet": item.get("sheet", ""),
                "excel_row": int(item.get("excel_row", 0)),
                "material": item.get("material", ""),
                "sap_code": item.get("sap_code", ""),
                "material_name": item.get("material_name", ""),
                "description": item.get("description", ""),
                "quantity": item.get("quantity", ""),
                "unit": item.get("unit", ""),
            }
        )
    return records


def handle_bom(row: dict[str, Any], bom_df: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """处理 BOM 前 12 个规格/对比/表格问题。

    参数：
        row：样例题原始对象。
        bom_df：标准化 BOM DataFrame。
    返回值：答案对象和 trace 对象。
    """

    question = row["question"]
    category = row.get("category_guess", "")
    suffixes_for_guard = extract_bom_order_suffixes(question)
    if any(word in question for word in ("对比", "不一样", "差异", "不一致")) and len(set(suffixes_for_guard)) < 2:
        reason = "BOM 对比题未提供两个不同订单/版本，标准答案标记为需追问，避免把同一订单硬做对比。"
        trace = make_trace(
            row["question_id"],
            "no_answer",
            BOM_SOURCE,
            [],
            [],
            {"order_suffix": suffixes_for_guard, "ambiguous_reason": "compare_requires_two_distinct_orders"},
            ["order_suffix", "material_name", "description"],
            "bom_compare_guard",
            len(bom_df),
            0,
            [{"step": "guard", "reason": reason}],
            reason,
        )
        return make_answer(row, "no_answer", category, "bom_compare_clarification", None, reason), trace
    selected, filters = select_bom_files(question, bom_df)
    if suffixes_for_guard and "model" not in filters:
        ambiguous_suffixes = []
        for suffix in suffixes_for_guard:
            matched = selected[selected["order_suffix"] == suffix]
            identity_count = matched[["order_no", "model", "file"]].drop_duplicates().shape[0]
            if identity_count > 1:
                ambiguous_suffixes.append({"order_suffix": suffix, "identity_count": int(identity_count)})
        if ambiguous_suffixes:
            reason = "订单尾号命中多个 BOM 实例，缺少客户/型号/文件版本等消歧条件，标准答案标记为需追问。"
            trace = make_trace(
                row["question_id"],
                "no_answer",
                BOM_SOURCE,
                sorted(selected["file"].unique().tolist()),
                sorted(selected["sheet"].unique().tolist()),
                {**filters, "ambiguous_suffixes": ambiguous_suffixes},
                ["order_suffix", "model", "file", "material_name", "description"],
                "bom_identity_ambiguity_guard",
                len(bom_df),
                int(len(selected)),
                [{"step": "guard", "ambiguous_suffixes": ambiguous_suffixes, "reason": reason}],
                reason,
            )
            return make_answer(row, "no_answer", category, "bom_order_identity_clarification", None, reason), trace
    materials = extract_bom_materials(question)
    matched = filter_bom_material_rows(selected, materials)
    files, sheets = source_files_and_sheets(matched)
    if selected.empty:
        reason = "未在 Phase 0 BOM 源数据中匹配到问题指定的订单号或型号。"
        trace = make_trace(
            row["question_id"],
            "no_answer",
            BOM_SOURCE,
            [],
            [],
            filters,
            ["order_suffix", "model", "material_name", "description"],
            "bom_file_select",
            len(bom_df),
            0,
            [{"step": "select_bom_file", "filters": filters, "matched_files": 0}],
            reason,
        )
        return make_answer(row, "no_answer", category, "bom_material_lookup", None, reason), trace
    if matched.empty:
        reason = "匹配到 BOM 文件，但未找到问题指定关键物料行。"
        trace = make_trace(
            row["question_id"],
            "no_answer",
            BOM_SOURCE,
            sorted(selected["file"].unique().tolist()),
            sorted(selected["sheet"].unique().tolist()),
            {**filters, "materials": materials},
            ["material_name", "description", "quantity", "unit"],
            "filter_material_rows",
            len(selected),
            0,
            [{"step": "filter_material_rows", "materials": materials, "matched_rows": 0}],
            reason,
        )
        return make_answer(row, "no_answer", category, "bom_material_lookup", None, reason), trace
    records = bom_rows_to_records(matched)
    answer: dict[str, Any] = {"rows": records}
    capability = "bom_material_table"
    aggregation = "select_material_spec_rows"
    if "对比" in question or "不一样" in question or "不一致" in question:
        capability = "bom_material_compare"
        aggregation = "compare_material_description_sets"
        grouped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for record in records:
            order_key = f"{record['order_suffix']}-{record['model']}-{record['version']}-{Path(record['file']).name}"
            grouped[order_key][record["material"]].append(record["description"])
        material_diff = []
        all_materials = sorted({record["material"] for record in records})
        for material in all_materials:
            values = {
                order_key: sorted(set(materials_map.get(material, [])))
                for order_key, materials_map in grouped.items()
            }
            unique_sets = {tuple(value) for value in values.values()}
            material_diff.append({"material": material, "different": len(unique_sets) > 1, "values": values})
        answer["comparison"] = material_diff
    elif "表格" in question or "EXCEL" in question.upper():
        capability = "bom_material_table"
    else:
        capability = "bom_material_spec"
    trace = make_trace(
        row["question_id"],
        "expected",
        BOM_SOURCE,
        files,
        sheets,
        {**filters, "materials": materials},
        ["material_name", "description", "quantity", "unit", "sap_code"],
        aggregation,
        len(selected),
        len(matched),
        [
            {"step": "select_bom_file", "filters": filters, "matched_files": len(files)},
            {"step": "filter_material_rows", "materials": materials, "matched_rows": len(records)},
            {"step": "trace_material_rows", "rows": records},
        ],
    )
    return make_answer(row, "expected", category, capability, answer), trace


def db_blocked_reason() -> str:
    """返回 2026 MySQL 题的阻塞原因。

    参数：无。
    返回值：阻塞原因。脚本只认可显式只读环境变量，避免误用业务写库配置。
    """

    readonly_url = os.getenv("EVAL_READONLY_DATABASE_URL") or os.getenv("PHASE1_READONLY_DATABASE_URL")
    if not readonly_url:
        return "未提供显式只读数据库连接配置 EVAL_READONLY_DATABASE_URL 或 PHASE1_READONLY_DATABASE_URL；为避免误用业务写库配置，本脚本未访问 MySQL。"
    lowered = readonly_url.lower()
    if "readonly" not in lowered and "read_only" not in lowered and "ro" not in lowered:
        return "检测到数据库连接配置，但无法从连接串确认只读身份；为避免写库风险，本脚本未访问 MySQL。"
    return "本 Phase 1 脚本尚未实现 2026 MySQL 只读 SQL 标准答案计算模板，按要求标记 blocked。"


def unsupported(row: dict[str, Any], reason: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """构造 unsupported 答案和 trace。

    参数：
        row：样例题原始对象。
        reason：不支持原因。
    返回值：答案对象和 trace 对象。
    """

    trace = make_trace(
        row["question_id"],
        "unsupported",
        "none",
        [],
        [],
        {},
        [],
        "unsupported",
        0,
        0,
        [{"step": "classify", "result": "unsupported", "reason": reason}],
        reason,
    )
    return make_answer(row, "unsupported", row.get("category_guess", ""), "unsupported", None, reason), trace


def no_answer(row: dict[str, Any], source: str, reason: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """构造 no_answer 答案和 trace。

    参数：
        row：样例题原始对象。
        source：已尝试的数据来源。
        reason：无答案原因。
    返回值：答案对象和 trace 对象。
    """

    trace = make_trace(
        row["question_id"],
        "no_answer",
        source,
        [],
        [],
        {},
        [],
        "no_answer",
        0,
        0,
        [{"step": "classify", "result": "no_answer", "reason": reason}],
        reason,
    )
    return make_answer(row, "no_answer", row.get("category_guess", ""), "no_answer", None, reason), trace


def build_known_values(logistics_df: pd.DataFrame) -> dict[str, list[str]]:
    """从历史物流数据中构造槽位候选值。

    参数：
        logistics_df：标准化历史物流 DataFrame。
    返回值：省份、城市、始发地、物流公司等候选值列表。
    """

    return {
        "provinces": sorted(logistics_df["province_norm"].dropna().unique().tolist()),
        "cities": sorted(logistics_df["city_norm"].dropna().unique().tolist()),
        "origins": sorted(logistics_df["origin_norm"].dropna().unique().tolist()),
        "carriers": sorted(logistics_df["carrier"].dropna().unique().tolist()),
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """写入 JSONL 文件。

    参数：
        path：输出路径。
        rows：待写入的字典列表。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(json_safe(row), ensure_ascii=False, separators=(",", ":")) + "\n")


def write_summary(path: Path, answers: list[dict[str, Any]], traces: list[dict[str, Any]]) -> None:
    """写入 expected_summary.md。

    参数：
        path：摘要输出路径。
        answers：标准答案列表。
        traces：trace 列表。
    返回值：无。
    """

    status_counts = Counter(answer["status"] for answer in answers)
    capability_counts = Counter(answer["capability"] for answer in answers if answer["status"] == "expected")
    category_counts = Counter(answer["category"] for answer in answers if answer["status"] == "expected")
    reason_counts = Counter(answer["reason"] for answer in answers if answer["status"] != "expected")
    lines = [
        "# E2E QA Phase 1 标准答案计算摘要",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        f"- 样例题总数：{len(answers)}",
        f"- trace 总数：{len(traces)}",
        "",
        "## 状态统计",
        "",
        "| 状态 | 数量 |",
        "| --- | ---: |",
    ]
    for status in ["expected", "no_answer", "blocked", "unsupported"]:
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.extend(["", "## expected 支持能力统计", "", "| 能力 | 数量 |", "| --- | ---: |"])
    for capability, count in capability_counts.most_common():
        lines.append(f"| {capability} | {count} |")
    lines.extend(["", "## expected 分类统计", "", "| 分类 | 数量 |", "| --- | ---: |"])
    for category, count in category_counts.most_common():
        lines.append(f"| {category} | {count} |")
    lines.extend(["", "## blocked/no_answer/unsupported 原因 Top 20", "", "| 原因 | 数量 |", "| --- | ---: |"])
    for reason, count in reason_counts.most_common(20):
        safe_reason = reason.replace("|", "\\|")
        lines.append(f"| {safe_reason} | {count} |")
    lines.extend(
        [
            "",
            "## 输出文件",
            "",
            "- `ai/eval/expected_answers/expected_answers.jsonl`",
            "- `ai/eval/expected_answers/expected_answer_trace.jsonl`",
            "- `ai/eval/expected_answers/expected_summary.md`",
            "",
            "## 计算边界",
            "",
            "- 所有 expected 数值均来自脚本对 Phase 0 Excel/xls 数据的聚合或物料行筛选。",
            "- 2026 MySQL 题未使用业务数据库连接；缺少显式只读配置时统一 blocked。",
            "- 未纳入 Phase 1 支持清单的派生分析、异常诊断、占比/同比/相关性等问题标记 unsupported。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def compute_expected(args: argparse.Namespace) -> dict[str, Any]:
    """执行 Phase 1 标准答案计算。

    参数：
        args：命令行参数对象。
    返回值：包含输出路径和状态统计的摘要字典。
    """

    root = repo_root_from_script()
    eval_dir = root / "ai" / "eval"
    sample_path = Path(args.sample_questions) if args.sample_questions else eval_dir / "sample_questions.jsonl"
    extract_root = Path(args.attachments_root) if args.attachments_root else eval_dir / "workdir" / "attachments_extracted"
    logistics_dir = extract_root / "23 年至 25 年物流源数据"
    bom_dir = extract_root / "BOM 源数据" / "BOM"
    output_dir = Path(args.output_dir) if args.output_dir else eval_dir / "expected_answers"
    logistics_df, _ = load_logistics_history(logistics_dir)
    bom_df, _ = load_bom_files(bom_dir)
    if logistics_df.empty:
        raise RuntimeError(f"未加载到历史物流 Excel 数据：{logistics_dir}")
    if bom_df.empty:
        raise RuntimeError(f"未加载到 BOM xls 数据：{bom_dir}")
    known = build_known_values(logistics_df)
    questions = read_questions(sample_path)
    answers: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for row in questions:
        domain = row.get("domain_guess", "")
        if domain == "bom":
            answer, trace = handle_bom(row, bom_df)
        elif domain == "logistics":
            answer, trace = handle_logistics(row, logistics_df, known)
        else:
            answer, trace = unsupported(row, "样例题领域无法识别，Phase 1 不计算标准答案。")
        trace_id = f"TRACE-{row['question_id']}"
        # 每条标准答案必须显式引用 trace，便于 Hermes 独立审查 expected 与计算来源是否一一对应。
        trace["trace_id"] = trace_id
        answer["trace_id"] = trace_id
        answers.append(answer)
        traces.append(trace)
    answers_path = output_dir / "expected_answers.jsonl"
    trace_path = output_dir / "expected_answer_trace.jsonl"
    summary_path = output_dir / "expected_summary.md"
    write_jsonl(answers_path, answers)
    write_jsonl(trace_path, traces)
    write_summary(summary_path, answers, traces)
    status_counts = Counter(answer["status"] for answer in answers)
    return {
        "answers_path": str(answers_path),
        "trace_path": str(trace_path),
        "summary_path": str(summary_path),
        "status_counts": dict(status_counts),
        "total_questions": len(questions),
        "total_traces": len(traces),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    """解析命令行参数。

    参数：
        argv：命令行参数列表。
    返回值：argparse Namespace。
    """

    parser = argparse.ArgumentParser(description="计算 E2E QA Phase 1 标准答案。")
    parser.add_argument("--sample-questions", default="", help="样例题 JSONL 路径，默认 ai/eval/sample_questions.jsonl。")
    parser.add_argument("--attachments-root", default="", help="Phase 0 解压目录，默认 ai/eval/workdir/attachments_extracted。")
    parser.add_argument("--output-dir", default="", help="输出目录，默认 ai/eval/expected_answers。")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """脚本入口。

    参数：
        argv：可选命令行参数；None 时读取 sys.argv。
    返回值：进程退出码，成功为 0。
    """

    args = parse_args(argv or sys.argv[1:])
    result = compute_expected(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
