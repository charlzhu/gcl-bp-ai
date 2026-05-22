"""
掌柜问数对齐 - Prompt 加载器。

对应掌柜问数 data-agent/app/prompt/prompt_loader.py。

所有 prompt 文件统一存放在 backend/app/prompts/zg/ 目录下，
通过 load_prompt(name) 按名称加载。

技术栈适配：
- 掌柜问数用 Path(__file__).parents[2] / 'prompts' 定位
- gcl-bp-ai 用相对于 prompts/zg/ 的路径
"""

from __future__ import annotations

from pathlib import Path


# prompt 文件根目录（从 business_qa_graph → domains → app → prompts/zg）
_PROMPTS_ROOT = Path(__file__).resolve().parent.parent.parent / "prompts" / "zg"


def load_prompt(name: str) -> str:
    """加载指定名称的 prompt 模板。

    参数：
        name: prompt 文件名（不含 .prompt 后缀），
              如 "extend_keywords_for_column_recall"。
    返回：
        prompt 模板内容字符串。
    异常：
        FileNotFoundError: prompt 文件不存在。
    """
    prompt_path = _PROMPTS_ROOT / f"{name}.prompt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"prompt 文件不存在: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def load_prompt_or_default(name: str, default: str = "") -> str:
    """安全加载 prompt，文件不存在时返回默认值。

    参数：
        name: prompt 文件名。
        default: 文件不存在时的默认返回值。
    返回：
        prompt 内容或默认值。
    """
    try:
        return load_prompt(name)
    except FileNotFoundError:
        return default
