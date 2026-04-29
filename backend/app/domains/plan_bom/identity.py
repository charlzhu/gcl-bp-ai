from __future__ import annotations

import hashlib
import re
from pathlib import Path


def normalize_identity_text(value: str | None) -> str:
    """归一化订单实例识别文本。

    参数：
        value: 原始订单号、订单名称或文件名文本。

    返回：
        便于做 Excel 开发期实例识别的归一化字符串。

    说明：
        这里的归一化仅服务于 Excel 开发期“内部实例键”生成，
        不能替代 BOM 的正式业务唯一键定义。
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"[\s_\-()（）/\\\\]+", "", text)


def normalize_file_instance_name(raw_file_name: str | None) -> str:
    """归一化文件实例识别用的文件名。

    参数：
        raw_file_name: 原始 Excel 文件名。

    返回：
        去掉目录、空白和常见分隔符后的归一化文件名。

    说明：
        1. 该结果只用于开发期 `file_instance_key` 兜底生成；
        2. 当文件哈ిష存在时，应优先用文件哈希识别文件实例，避免重命名导致实例键变化。
    """
    file_stem = Path(str(raw_file_name)).stem if raw_file_name else None
    return normalize_identity_text(file_stem)


def build_order_display_label(order_name: str | None, raw_file_name: str | None, order_no: str) -> str:
    """构造候选展示标签。

    参数：
        order_name: 解析出的订单名称；
        raw_file_name: 原始 Excel 文件名；
        order_no: 标准订单号。

    返回：
        前端或抽验报告可直接展示的候选标签。
    """
    if order_name and order_name.strip():
        return order_name.strip()
    if raw_file_name and str(raw_file_name).strip():
        return Path(str(raw_file_name)).stem
    return order_no


def build_order_identity_key(order_no: str, order_name: str | None, raw_file_name: str | None) -> str:
    """生成 Excel 开发期内部实例键。

    参数：
        order_no: 标准订单号；
        order_name: 解析出的订单名称；
        raw_file_name: 原始 Excel 文件名。

    返回：
        稳定的内部实例键。

    说明：
        1. 该字段只用于 Excel 开发期的导入覆盖控制、候选识别和定位；
        2. 它不是正式业务主键，也不替代“订单号 + 版本号”的业务语义；
        3. 当同一标准订单号下存在多个业务实例时，用它把实例区分开。
    """
    normalized_order_no = normalize_identity_text(order_no)
    display_basis = normalize_identity_text(order_name) or normalize_identity_text(Path(raw_file_name).stem if raw_file_name else None)
    identity_basis = display_basis or normalized_order_no
    digest = hashlib.sha1(f"{normalized_order_no}|{identity_basis}".encode("utf-8")).hexdigest()
    return f"excel_inst_{digest}"


def build_file_instance_key(
    order_identity_key: str,
    version_no: str,
    source_type: str,
    raw_file_name: str | None,
    file_hash: str | None,
) -> str:
    """生成 Excel 开发期文件实例键。

    参数：
        order_identity_key: 已确认的业务实例内部键；
        version_no: BOM 版本号；
        source_type: 来源类型；
        raw_file_name: 原始 Excel 文件名；
        file_hash: Excel 文件哈希。

    返回：
        稳定的开发期文件实例键。

    说明：
        1. `file_instance_key` 只用于“同一业务实例、同一版本下多文件并存”场景；
        2. 它不替代正式业务唯一键，也不替代 `order_identity_key`；
        3. 当文件哈希存在时，优先使用文件哈希，避免同文件重命名导致实例识别不稳；
        4. 当文件哈希缺失时，退化使用归一化文件名，确保历史数据仍可回填实例键。
    """
    normalized_version = normalize_identity_text(version_no)
    normalized_source = normalize_identity_text(source_type)
    normalized_hash = normalize_identity_text(file_hash)
    normalized_name = normalize_file_instance_name(raw_file_name)
    if normalized_hash:
        identity_basis = f"hash:{normalized_hash}"
    else:
        identity_basis = f"name:{normalized_name}"
    digest = hashlib.sha1(
        f"{order_identity_key}|{normalized_version}|{normalized_source}|{identity_basis}".encode("utf-8")
    ).hexdigest()
    return f"excel_file_{digest}"
