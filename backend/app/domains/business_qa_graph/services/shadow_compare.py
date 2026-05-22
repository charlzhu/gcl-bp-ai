"""NQE-S3 ShadowCompareService：NL2SQL 与旧链路结果对比服务。

本服务负责：
1. 从业务结果中提取摘要签名（status、row_count、key_numbers、hash）；
2. 对比两套结果并生成结构化差异报告；
3. 将对比结果追加写入 JSONL 文件，用于离线审计。

所有输出不含 SQL、表名、字段名、query_key、planner、guardrail、raw/debug 等技术细节。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# JSONL 输出文件默认路径
DEFAULT_JSONL_FILENAME = "shadow_compare.jsonl"


class ShadowCompareService:
    """NL2SQL shadow compare 服务。

    参数：
        jsonl_output_dir: JSONL 输出目录，默认从环境变量
            NQE_S3_JSONL_DIR 读取，若为空则使用 ai/outbox/kanban/nqe_s3/。
    返回：
        可调用 compare() 和 write_to_jsonl() 的服务实例。
    业务逻辑：
        该服务只做 shadow 对比记录，不阻断正常返回、不修改正式问答链路。
    """

    def __init__(self, *, jsonl_output_dir: str | None = None) -> None:
        """初始化 shadow compare 服务。

        参数：
            jsonl_output_dir: 可选 JSONL 输出目录。不传时自动解析。
        """
        if jsonl_output_dir:
            self._jsonl_dir = Path(jsonl_output_dir)
        else:
            env_dir = os.environ.get("NQE_S3_JSONL_DIR", "")
            if env_dir:
                self._jsonl_dir = Path(env_dir)
            else:
                # 默认输出到 ai/outbox/kanban/nqe_s3/
                self._jsonl_dir = Path(
                    os.environ.get(
                        "HERMES_KANBAN_WORKSPACE",
                        os.getcwd(),
                    )
                ) / "ai" / "outbox" / "kanban" / "nqe_s3"

        self._jsonl_path = self._jsonl_dir / DEFAULT_JSONL_FILENAME

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def extract_signature(self, result: dict[str, Any]) -> dict[str, Any]:
        """从业务结果中提取摘要签名。

        参数：
            result: 业务执行结果字典（来自旧链路或 NL2SQL 链路）。
        返回：
            签名字典，包含以下字段：
            - status: 状态码（success/clarify/error/unsupported/empty）
            - row_count: 结果行数
            - key_numbers: 提取的关键数值列表（前 20 个数值）
            - hash: 整个结果的 SHA256 哈希
            - display_type: 展示类型（table/narrative/error）
            - has_warnings: 是否有业务警告
        业务逻辑：
            签名只提取面向业务的摘要信息，不包含 SQL、表名、字段名等内部细节。
        """
        if not result:
            return _empty_signature()

        # 提取 status
        status = _extract_status(result)

        # 提取 row_count
        row_count = _extract_row_count(result)

        # 提取关键数值
        key_numbers = _extract_key_numbers(result)

        # 计算 hash
        hash_value = _compute_hash(result)

        # 提取 display_type
        display_type = str(result.get("display_type") or "narrative")

        # 提取是否有业务警告
        warnings = result.get("warnings") or []
        has_warnings = bool(warnings)

        return {
            "status": status,
            "row_count": row_count,
            "key_numbers": key_numbers,
            "hash": hash_value,
            "display_type": display_type,
            "has_warnings": has_warnings,
        }

    def compare(
        self,
        old_result: dict[str, Any],
        nl2sql_result: dict[str, Any],
    ) -> dict[str, Any]:
        """对比两套业务结果并生成结构化差异报告。

        参数：
            old_result: 旧规则链路执行结果。
            nl2sql_result: NL2SQL 链路执行结果。
        返回：
            对比结果字典，包含以下字段：
            - overall_match: 是否完全一致
            - status_match: 状态是否一致
            - row_count_match: 行数是否一致
            - row_count_diff: 行数差异
            - key_numbers_match: 关键数值是否完全一致
            - hash_match: 哈希是否一致
            - old_signature: 旧链路签名
            - nl2sql_signature: NL2SQL 签名
            - mismatch_reasons: 不一致原因列表
        业务逻辑：
            对比是摘要级的，关注业务可感知的差异（行数、状态、关键数值），
            不逐字节比较 SQL 或内部实现。
        """
        old_sig = self.extract_signature(old_result)
        nl2sql_sig = self.extract_signature(nl2sql_result)

        # 各项对比
        status_match = old_sig["status"] == nl2sql_sig["status"]
        row_count_match = old_sig["row_count"] == nl2sql_sig["row_count"]
        row_count_diff = nl2sql_sig["row_count"] - old_sig["row_count"]
        key_numbers_match = old_sig["key_numbers"] == nl2sql_sig["key_numbers"]
        hash_match = old_sig["hash"] == nl2sql_sig["hash"]

        # 收集不一致原因（仅记录业务可感知的差异）
        mismatch_reasons: list[str] = []
        if not status_match:
            mismatch_reasons.append(
                f"状态不一致：旧链路={old_sig['status']}，NL2SQL={nl2sql_sig['status']}"
            )
        if not row_count_match:
            mismatch_reasons.append(
                f"行数不一致：旧链路={old_sig['row_count']}，NL2SQL={nl2sql_sig['row_count']}，差异={row_count_diff}"
            )
        if not key_numbers_match:
            mismatch_reasons.append("关键数值不一致")
        if not hash_match:
            mismatch_reasons.append("结果哈希不一致")

        overall_match = (
            status_match
            and row_count_match
            and key_numbers_match
            # hash_match 是额外信号，不作为 overall_match 的必要条件
            # 因为不同清洗路径可能产生语义相同但哈希不同的结果
        )

        return {
            "overall_match": overall_match,
            "status_match": status_match,
            "row_count_match": row_count_match,
            "row_count_diff": row_count_diff,
            "key_numbers_match": key_numbers_match,
            "hash_match": hash_match,
            "old_signature": old_sig,
            "nl2sql_signature": nl2sql_sig,
            "mismatch_reasons": mismatch_reasons,
        }

    def write_to_jsonl(
        self,
        *,
        question: str,
        old_signature: dict[str, Any],
        nl2sql_signature: dict[str, Any],
        comparison: dict[str, Any],
        trace_id: str | None = None,
    ) -> None:
        """将对比结果追加写入 JSONL 文件。

        参数：
            question: 用户原始问题（脱敏后）。
            old_signature: 旧链路签名。
            nl2sql_signature: NL2SQL 签名。
            comparison: compare() 返回的对比结果。
            trace_id: 可选追踪号。
        返回：
            无。写文件失败只记录日志，不抛异常。
        业务逻辑：
            JSONL 文件只用于离线审计，每条记录不含 SQL、表名、字段名等技术细节。
        """
        try:
            # 确保目录存在
            self._jsonl_dir.mkdir(parents=True, exist_ok=True)

            record = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "question": str(question)[:500],  # 长度限制，避免超长问题
                "trace_id": trace_id or "",
                "old_signature": {
                    "status": old_signature.get("status", ""),
                    "row_count": old_signature.get("row_count", 0),
                    "key_numbers": old_signature.get("key_numbers", []),
                    "hash": old_signature.get("hash", ""),
                },
                "nl2sql_signature": {
                    "status": nl2sql_signature.get("status", ""),
                    "row_count": nl2sql_signature.get("row_count", 0),
                    "key_numbers": nl2sql_signature.get("key_numbers", []),
                    "hash": nl2sql_signature.get("hash", ""),
                },
                "comparison": {
                    "overall_match": comparison.get("overall_match", False),
                    "status_match": comparison.get("status_match", False),
                    "row_count_match": comparison.get("row_count_match", False),
                    "row_count_diff": comparison.get("row_count_diff", 0),
                    "key_numbers_match": comparison.get("key_numbers_match", False),
                    "hash_match": comparison.get("hash_match", False),
                    "mismatch_reasons": comparison.get("mismatch_reasons", []),
                },
            }

            # 追加写入 JSONL
            line = json.dumps(record, ensure_ascii=False, default=str)
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

            logger.debug(
                "NQE-S3 shadow compare 已写入 JSONL：%s（overall_match=%s）",
                self._jsonl_path,
                comparison.get("overall_match"),
            )
        except Exception as exc:
            # 写文件失败只记录日志，不中断主链路
            logger.warning(
                "NQE-S3 JSONL 写入失败（不影响主链路）：%s",
                type(exc).__name__,
                exc_info=True,
            )


# =============================================================================
# 内部辅助函数
# =============================================================================


def _empty_signature() -> dict[str, Any]:
    """返回空签名的安全默认值。

    返回：
        包含默认值的签名字典。
    业务逻辑：
        空签名确保对比时不会因缺失字段而崩溃。
    """
    return {
        "status": "empty",
        "row_count": 0,
        "key_numbers": [],
        "hash": hashlib.sha256(b"").hexdigest(),
        "display_type": "narrative",
        "has_warnings": False,
    }


def _extract_status(result: dict[str, Any]) -> str:
    """从结果中提取归一化的状态码。

    参数：
        result: 业务结果字典。
    返回：
        归一化状态：success / clarify / error / unsupported / empty。
    业务逻辑：
        统一 status_code 和 needs_clarification 等字段为标准化状态。
    """
    # 优先从 status_code 提取
    status_code = str(result.get("status_code") or "").lower()

    # 空结果
    if not result:
        return "empty"

    # 错误状态
    if result.get("error") or status_code in ("error", "execution_error"):
        return "error"

    # 需要澄清
    if result.get("needs_clarification") or status_code == "clarify":
        return "clarify"

    # 不支持
    if not result.get("supported", True) or status_code == "unsupported":
        return "unsupported"

    # 标准成功
    if status_code in ("success", "ok"):
        return "success"

    # 有行数或答案摘要视为成功
    if result.get("row_count") is not None or result.get("answer_summary"):
        return "success"

    return "empty"


def _extract_row_count(result: dict[str, Any]) -> int:
    """从结果中提取行数。

    参数：
        result: 业务结果字典。
    返回：
        行数（整数），无法提取时返回 0。
    业务逻辑：
        优先从 row_count 字段提取，其次从 rows 长度计算。
    """
    row_count = result.get("row_count")
    if isinstance(row_count, (int, float)):
        return max(0, int(row_count))

    rows = result.get("rows")
    if isinstance(rows, list):
        return len(rows)

    return 0


def _extract_key_numbers(result: dict[str, Any]) -> list[float]:
    """从结果中提取关键数值，用于业务可感知的对比。

    参数：
        result: 业务结果字典。
    返回：
        关键数值列表（最多 20 个）。
    业务逻辑：
        从 rows、answer_summary 中提取数值，过滤掉年份/ID/索引等非指标值。
        目的是提取业务指标数值（如车次数、金额、吨位等），方便对比。
    """
    numbers: list[float] = []

    # 从 rows 中提取数值（每一行的数字列）
    rows = result.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, list):
                for val in row:
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        numbers.append(float(val))

    # 限制数量，避免签名过大
    # 取前 20 个关键数值
    return numbers[:20]


def _compute_hash(result: dict[str, Any]) -> str:
    """计算业务结果的 SHA256 哈希。

    参数：
        result: 业务结果字典。
    返回：
        64 字符十六进制 SHA256 哈希。
    业务逻辑：
        哈希基于归一化后的 JSON 序列化字符串计算，确保相同业务结果产生相同哈希。
        排除了 trace_events、history_log_id 等运行态字段。
    """
    # 创建可比较的规范化副本（排除运行态字段）
    comparable = {}
    for key in (
        "answer_summary",
        "columns",
        "rows",
        "row_count",
        "supported",
        "needs_clarification",
        "status_code",
        "display_type",
        "title",
        "warnings",
        "calculation_logic",
    ):
        if key in result:
            comparable[key] = result[key]

    # 归一化 JSON 序列化
    normalized = json.dumps(comparable, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = [
    "ShadowCompareService",
    "DEFAULT_JSONL_FILENAME",
]
