/// <reference types="vite/client" />

/**
 * Vite 环境变量声明。
 * 说明：
 * 当前前端直接读取 API 地址和应用标题，因此在严格模式下补齐类型定义。
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_API_PREFIX?: string
  readonly VITE_APP_TITLE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
