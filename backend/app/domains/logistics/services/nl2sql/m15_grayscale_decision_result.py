"""M15：灰度决策结果模型——标记是否灰度替换及替换后的结果。"""

from __future__ import annotations

from pydantic import BaseModel

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult

# 环境变量：灰度启用的域+问题类型。
# 新格式（JSON）：NL2SQL_GRAYSCALE_CONFIG='{"logistics": ["simple_aggregate"], "business_analysis": ["summary"]}'
# 旧格式（兼容）：LOGISTICS_NL2SQL_GRAYSCALE_TYPES="simple_aggregate,dimension_split"
GRAYSCALE_TYPES_ENV_FLAG = "LOGISTICS_NL2SQL_GRAYSCALE_TYPES"
GRAYSCALE_CONFIG_ENV_FLAG = "NL2SQL_GRAYSCALE_CONFIG"
# 默认域（旧格式兼容）
DEFAULT_GRAYSCALE_DOMAIN = "logistics"


class LogisticsNl2SqlGrayscaleDecisionResult(BaseModel):
    """灰度决策带替换结果。

    参数：
        should_grayscale: 是否应灰度替换。
        replacement_result: 替换后的 NL2SQL 结果（仅 should_grayscale=True 时有效）。
        fallback_reason: 不灰度时的原因；正常灰度时 None。
        domain: 灰度决策所属的业务域，用于审计日志。
    """

    should_grayscale: bool = False
    replacement_result: LogisticsDataQaResult | None = None
    fallback_reason: str | None = None
    domain: str = "logistics"


__all__ = [
    "GRAYSCALE_TYPES_ENV_FLAG",
    "GRAYSCALE_CONFIG_ENV_FLAG",
    "DEFAULT_GRAYSCALE_DOMAIN",
    "LogisticsNl2SqlGrayscaleDecisionResult",
]
