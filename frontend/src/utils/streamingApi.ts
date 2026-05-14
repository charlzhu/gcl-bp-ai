import { buildApiUrl } from '@/utils/http'

export type JsonLineStreamEventName = 'meta' | 'delta' | 'done' | 'error' | string

export interface JsonLineStreamEvent<TDone> {
  event: JsonLineStreamEventName
  data: {
    text?: string
    answer?: string
    message?: string
    data?: TDone
    [key: string]: any
  }
}

export interface JsonLineStreamHandlers<TDone> {
  onMeta?: (data: JsonLineStreamEvent<TDone>['data']) => void
  onDelta?: (text: string, data: JsonLineStreamEvent<TDone>['data']) => void
  onDone?: (data: TDone, eventData: JsonLineStreamEvent<TDone>['data']) => void
  onError?: (message: string, eventData?: JsonLineStreamEvent<TDone>['data']) => void
}

/**
 * 使用 fetch + ReadableStream 消费后端 NDJSON 流式接口。
 *
 * 参数：
 *   path: 后端相对 API 路径。
 *   payload: POST JSON 请求体。
 *   handlers: meta/delta/done/error 事件回调。
 *
 * 返回值：
 *   Promise<void>，done 或 error 事件处理完成后结束。
 *
 * 业务逻辑：
 *   后端会先完成确定性查询，再把问题和结果送入 LLM 表达层。前端只增量展示
 *   delta 文本，并在 done 事件到达后渲染确定性结构化表格。
 */
export async function postJsonLineStream<TDone>(
  path: string,
  payload: Record<string, any>,
  handlers: JsonLineStreamHandlers<TDone>,
) {
  const response = await fetch(buildApiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`流式接口请求失败：${response.status}`)
  }
  const body: ReadableStream<Uint8Array> | null = response.body
  if (!body) {
    throw new Error('当前浏览器不支持流式回答，请刷新后重试。')
  }

  const reader = body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let doneSeen = false

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      doneSeen = dispatchJsonLineEvent(line, handlers) || doneSeen
    }
  }

  const tail = `${buffer}${decoder.decode()}`.trim()
  if (tail) {
    doneSeen = dispatchJsonLineEvent(tail, handlers) || doneSeen
  }
  if (!doneSeen) {
    throw new Error('流式回答未正常结束，请稍后重试。')
  }
}

/** 解析并分发单行 NDJSON 事件。 */
function dispatchJsonLineEvent<TDone>(line: string, handlers: JsonLineStreamHandlers<TDone>) {
  const trimmed = line.trim()
  if (!trimmed) return false
  const event = JSON.parse(trimmed) as JsonLineStreamEvent<TDone>
  const eventData = event.data || {}
  if (event.event === 'meta') {
    handlers.onMeta?.(eventData)
    return false
  }
  if (event.event === 'delta') {
    handlers.onDelta?.(String(eventData.text || ''), eventData)
    return false
  }
  if (event.event === 'done') {
    handlers.onDone?.(eventData.data as TDone, eventData)
    return true
  }
  if (event.event === 'error') {
    const message = String(eventData.message || '流式回答失败，请稍后重试。')
    handlers.onError?.(message, eventData)
    throw new Error(message)
  }
  return false
}
