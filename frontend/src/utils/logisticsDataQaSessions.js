const LOGISTICS_DATA_QA_SESSION_LIST_KEY = 'logistics:data-qa:sessions';
const LOGISTICS_DATA_QA_SESSION_DATA_PREFIX = 'logistics:data-qa:session:';
const LOGISTICS_DATA_QA_ACTIVE_SESSION_KEY = 'logistics:data-qa:active-session';
const LOGISTICS_DATA_QA_SESSION_EVENT = 'logistics-data-qa-sessions-updated';
/**
 * 读取物流数据问答会话摘要列表。
 * 说明：
 * 1. 这里只保存侧边栏展示需要的最小字段；
 * 2. 会话完整内容单独按会话 ID 存储，避免摘要列表过重。
 */
export function listLogisticsDataQaSessions() {
    const raw = sessionStorage.getItem(LOGISTICS_DATA_QA_SESSION_LIST_KEY);
    if (!raw)
        return [];
    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed))
            return [];
        return parsed.filter(isSessionSummary);
    }
    catch (_error) {
        return [];
    }
}
/**
 * 读取单个物流数据问答会话。
 */
export function getLogisticsDataQaSession(sessionId) {
    const raw = sessionStorage.getItem(`${LOGISTICS_DATA_QA_SESSION_DATA_PREFIX}${sessionId}`);
    if (!raw)
        return null;
    try {
        const parsed = JSON.parse(raw);
        return normalizeSessionRecord(parsed);
    }
    catch (_error) {
        return null;
    }
}
/**
 * 保存物流数据问答会话。
 * 说明：
 * 1. 每次保存都会同时刷新侧边栏摘要；
 * 2. 摘要列表按最近更新时间倒序展示，符合持续对话使用习惯。
 */
export function saveLogisticsDataQaSession(record) {
    const normalized = normalizeSessionRecord(record);
    if (!normalized)
        return;
    sessionStorage.setItem(`${LOGISTICS_DATA_QA_SESSION_DATA_PREFIX}${normalized.id}`, JSON.stringify(normalized));
    const summaries = listLogisticsDataQaSessions().filter((item) => item.id !== normalized.id);
    summaries.unshift({
        id: normalized.id,
        title: normalized.title,
        preview: normalized.preview,
        updatedAt: normalized.updatedAt,
    });
    sessionStorage.setItem(LOGISTICS_DATA_QA_SESSION_LIST_KEY, JSON.stringify(summaries));
    setActiveLogisticsDataQaSessionId(normalized.id);
    emitLogisticsDataQaSessionUpdated();
}
/**
 * 删除指定会话。
 */
export function removeLogisticsDataQaSession(sessionId) {
    sessionStorage.removeItem(`${LOGISTICS_DATA_QA_SESSION_DATA_PREFIX}${sessionId}`);
    const summaries = listLogisticsDataQaSessions().filter((item) => item.id !== sessionId);
    sessionStorage.setItem(LOGISTICS_DATA_QA_SESSION_LIST_KEY, JSON.stringify(summaries));
    if (getActiveLogisticsDataQaSessionId() === sessionId) {
        if (summaries.length) {
            setActiveLogisticsDataQaSessionId(summaries[0].id);
        }
        else {
            clearActiveLogisticsDataQaSessionId();
        }
    }
    emitLogisticsDataQaSessionUpdated();
}
/**
 * 更新指定会话标题。
 * 说明：
 * 重命名只更新标题本身，不改对话内容和最近预览。
 */
export function renameLogisticsDataQaSession(sessionId, title) {
    const session = getLogisticsDataQaSession(sessionId);
    if (!session)
        return;
    saveLogisticsDataQaSession({
        ...session,
        title,
    });
}
/**
 * 记录当前激活会话 ID。
 */
export function setActiveLogisticsDataQaSessionId(sessionId) {
    sessionStorage.setItem(LOGISTICS_DATA_QA_ACTIVE_SESSION_KEY, sessionId);
}
/**
 * 读取当前激活会话 ID。
 */
export function getActiveLogisticsDataQaSessionId() {
    return sessionStorage.getItem(LOGISTICS_DATA_QA_ACTIVE_SESSION_KEY) || '';
}
/**
 * 清理当前激活会话 ID。
 */
export function clearActiveLogisticsDataQaSessionId() {
    sessionStorage.removeItem(LOGISTICS_DATA_QA_ACTIVE_SESSION_KEY);
}
/**
 * 派发会话更新事件，供页面同步侧边栏。
 */
export function emitLogisticsDataQaSessionUpdated() {
    window.dispatchEvent(new CustomEvent(LOGISTICS_DATA_QA_SESSION_EVENT));
}
/**
 * 返回会话更新事件名。
 */
export function getLogisticsDataQaSessionEventName() {
    return LOGISTICS_DATA_QA_SESSION_EVENT;
}
/**
 * 生成新会话 ID。
 */
export function buildLogisticsDataQaSessionId() {
    return `logistics-qa-session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
/**
 * 根据问题文本生成会话标题。
 * 说明：
 * 标题优先使用首问前 18 个字符，避免侧边栏标题过长。
 */
export function buildLogisticsDataQaSessionTitle(question) {
    const normalized = String(question || '').trim();
    if (!normalized)
        return '新建对话';
    return normalized.length > 18 ? `${normalized.slice(0, 18)}…` : normalized;
}
/**
 * 根据最后一轮结果生成会话预览。
 * 说明：
 * 预览优先展示结果摘要；如果没有结果，则退回问题本身。
 */
export function buildLogisticsDataQaSessionPreview(turn) {
    if (!turn)
        return '等待开始新的业务问题';
    const resultSummary = turn.result && typeof turn.result.answer_summary === 'string'
        ? turn.result.answer_summary
        : '';
    const preview = resultSummary || turn.requestError || turn.question;
    return preview.length > 34 ? `${preview.slice(0, 34)}…` : preview;
}
/**
 * 判断摘要结构是否合法。
 */
function isSessionSummary(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const raw = value;
    return (typeof raw.id === 'string' &&
        typeof raw.title === 'string' &&
        typeof raw.preview === 'string' &&
        typeof raw.updatedAt === 'string');
}
/**
 * 将任意对象归一化为合法会话结构。
 * 说明：
 * 1. 防止无效历史数据破坏会话列表；
 * 2. items 里只保留结构完整的轮次。
 */
function normalizeSessionRecord(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return null;
    const raw = value;
    if (typeof raw.id !== 'string' || typeof raw.title !== 'string' || !Array.isArray(raw.items)) {
        return null;
    }
    const items = raw.items.filter(isSessionTurn);
    const latestTurn = items[items.length - 1] ?? null;
    return {
        id: raw.id,
        title: raw.title,
        preview: typeof raw.preview === 'string' && raw.preview.trim()
            ? raw.preview
            : buildLogisticsDataQaSessionPreview(latestTurn),
        updatedAt: typeof raw.updatedAt === 'string' && raw.updatedAt
            ? raw.updatedAt
            : latestTurn?.answeredAt || new Date().toISOString(),
        items,
    };
}
/**
 * 判断单条对话轮次是否合法。
 */
function isSessionTurn(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const raw = value;
    return (typeof raw.id === 'string' &&
        typeof raw.question === 'string' &&
        typeof raw.askedAt === 'string' &&
        typeof raw.answeredAt === 'string' &&
        typeof raw.source === 'string' &&
        typeof raw.requestError === 'string' &&
        typeof raw.showAdvancedInfo === 'boolean' &&
        (raw.historyLogId === null || typeof raw.historyLogId === 'number') &&
        (raw.result === null || (typeof raw.result === 'object' && !Array.isArray(raw.result))));
}
