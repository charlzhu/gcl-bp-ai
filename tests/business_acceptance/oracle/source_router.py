from __future__ import annotations

import re
from dataclasses import asdict, dataclass


EXCEL_SOURCE = "excel"
MYSQL_SOURCE = "mysql"
UNSUPPORTED_SOURCE = "unsupported"

HISTORICAL_EXCEL_YEARS = {2023, 2024, 2025}
MYSQL_START_YEAR = 2026


@dataclass(frozen=True)
class LogisticsSourceRoute:
    """物流年份到标准答案数据源的路由结果。

    参数：
        year：业务问题中识别出的四位年份。
        source：标准答案数据源，当前支持 excel / mysql / unsupported。
        reason：路由原因，供报告和排查使用。
    返回值：无。
    """

    year: int
    source: str
    reason: str

    def to_dict(self) -> dict[str, int | str]:
        """转换为可 JSON 序列化的字典。

        参数：无。
        返回值：包含 year、source、reason 的字典。
        """

        return asdict(self)


def normalize_year_token(token: str) -> int | None:
    """把问题中的年份片段归一为四位年份。

    参数：
        token：正则识别出的年份片段，例如 `2025` 或 `25`。
    返回值：
        四位年份；无法归一时返回 None。

    业务逻辑：
        当前业务问题集中常见 `23年`、`24年`、`25年` 这类简写。
        P2.1 只处理 2023 年及之后的物流验收口径，因此两位年份只接受 23 及以上。
    """

    if not token.isdigit():
        return None
    if len(token) == 4:
        return int(token)
    if len(token) == 2:
        year = 2000 + int(token)
        if year >= 2023:
            return year
    return None


def extract_logistics_years(question: str) -> list[int]:
    """从物流问题文本中提取可路由年份。

    参数：
        question：业务问题文本。
    返回值：
        按出现顺序去重后的四位年份列表。
    """

    years: list[int] = []
    seen: set[int] = set()
    compact = re.sub(r"\s+", "", question)
    for matched in re.finditer(r"(?<!\d)(20\d{2}|\d{2})年", compact):
        year = normalize_year_token(matched.group(1))
        if year is None or year in seen:
            continue
        years.append(year)
        seen.add(year)
    return years


def route_logistics_year(year: int) -> LogisticsSourceRoute:
    """按物流年份规则路由标准答案数据源。

    参数：
        year：四位业务年份。
    返回值：
        LogisticsSourceRoute 路由结果。

    业务逻辑：
        2023-2025 年走历史 Excel；2026 年及以后走正式 MySQL。
        2023 年前不属于当前物流一期标准答案计算器范围，显式标记为 unsupported。
    """

    if year in HISTORICAL_EXCEL_YEARS:
        return LogisticsSourceRoute(
            year=year,
            source=EXCEL_SOURCE,
            reason="2023-2025 年物流历史数据来自 Excel。",
        )
    if year >= MYSQL_START_YEAR:
        return LogisticsSourceRoute(
            year=year,
            source=MYSQL_SOURCE,
            reason="2026 年及以后物流正式数据来自 MySQL。",
        )
    return LogisticsSourceRoute(
        year=year,
        source=UNSUPPORTED_SOURCE,
        reason="2023 年前不在当前物流 Oracle Engine 数据源范围内。",
    )


def route_logistics_sources(question: str) -> list[LogisticsSourceRoute]:
    """从问题文本提取年份并完成物流数据源路由。

    参数：
        question：业务问题文本。
    返回值：
        路由结果列表；未识别年份时返回空列表。
    """

    return [route_logistics_year(year) for year in extract_logistics_years(question)]

