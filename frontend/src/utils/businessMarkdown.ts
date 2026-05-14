/**
 * 业务智能问答 Markdown 渲染工具。
 *
 * 设计边界：
 * 1. 只支持答案正文常用的段落、标题、无序/有序列表、加粗和行内代码；
 * 2. 所有原始文本先做 HTML 转义，再转换少量受控 Markdown 标记；
 * 3. 不解析链接、图片、表格或任意 HTML，避免 v-html 引入 XSS 风险；
 * 4. 结构化表格仍由后端确定性 payload 和前端表格组件展示，不在 Markdown 中渲染。
 */

const blankLinePattern = /^\s*$/
const unorderedListPattern = /^\s*[-*]\s+(.+)$/
const orderedListPattern = /^\s*\d+[.)]\s+(.+)$/
const headingPattern = /^\s*(#{1,4})\s+(.+)$/

/**
 * 将业务答案 Markdown 渲染为受控 HTML。
 *
 * 参数：
 *   markdown: 后端 LLM 表达层返回的答案正文。
 *
 * 返回值：
 *   已转义并转换少量 Markdown 标记的 HTML，可安全用于 v-html。
 */
export function renderBusinessMarkdown(markdown: string | null | undefined): string {
  const source = String(markdown || '').replace(/\r\n?/g, '\n').trim()
  if (!source) return ''

  const blocks: string[] = []
  let paragraphLines: string[] = []
  let listItems: string[] = []
  let listType: 'ul' | 'ol' | null = null

  const flushParagraph = () => {
    if (!paragraphLines.length) return
    blocks.push(`<p>${paragraphLines.map(renderInlineMarkdown).join('<br />')}</p>`)
    paragraphLines = []
  }

  const flushList = () => {
    if (!listItems.length || !listType) return
    blocks.push(`<${listType}>${listItems.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</${listType}>`)
    listItems = []
    listType = null
  }

  for (const rawLine of source.split('\n')) {
    if (blankLinePattern.test(rawLine)) {
      flushParagraph()
      flushList()
      continue
    }

    const headingMatch = rawLine.match(headingPattern)
    if (headingMatch) {
      flushParagraph()
      flushList()
      const level = Math.min(headingMatch[1].length + 2, 4)
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`)
      continue
    }

    const unorderedMatch = rawLine.match(unorderedListPattern)
    if (unorderedMatch) {
      flushParagraph()
      if (listType && listType !== 'ul') flushList()
      listType = 'ul'
      listItems.push(unorderedMatch[1])
      continue
    }

    const orderedMatch = rawLine.match(orderedListPattern)
    if (orderedMatch) {
      flushParagraph()
      if (listType && listType !== 'ol') flushList()
      listType = 'ol'
      listItems.push(orderedMatch[1])
      continue
    }

    flushList()
    paragraphLines.push(rawLine.trim())
  }

  flushParagraph()
  flushList()
  return blocks.join('')
}

/** 将行内 Markdown 标记转换为受控 HTML，转换前先转义所有原始文本。 */
function renderInlineMarkdown(text: string): string {
  return escapeHtml(text)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
}

/** HTML 转义，防止 LLM 或历史消息中的 HTML 被 v-html 执行。 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
