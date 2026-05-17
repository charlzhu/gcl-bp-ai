from pathlib import Path


COMPONENT_PATH = Path(__file__).resolve().parents[2] / "frontend" / "src" / "views" / "business-chat" / "BusinessChatPage.vue"


def _secondary_actions_block() -> str:
    """读取智能助手结果卡片的二级操作模板片段。"""
    text = COMPONENT_PATH.read_text(encoding="utf-8")
    start = text.index('class="answer-secondary-actions"')
    end = text.index('<div v-if="buildResultSummaryItems(message).length"', start)
    return text[start:end]


def test_business_chat_secondary_actions_hide_unavailable_buttons() -> None:
    """无可用数据时不应展示点不开的二级按钮，避免用户误以为可以继续操作。"""
    block = _secondary_actions_block()

    assert 'v-if="hasAssistantBasis(message)"' in block
    assert block.count('v-if="hasAssistantAuditRows(message)"') == 2
    assert ':disabled=' not in block
