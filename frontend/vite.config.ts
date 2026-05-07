import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

/**
 * Vite 配置
 * 说明：
 * 1. 前端浏览器侧默认访问同源 `/api/v1`，避免 Chrome Private Network Access 告警；
 * 2. 本地开发通过 dev proxy 把 `/api/v1` 转发到后端；
 * 3. 默认开发端口可通过环境变量 VITE_PORT 覆盖。
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = Number(env.VITE_PORT || 5173)
  const apiPrefix = normalizeApiPrefix(env.VITE_API_PREFIX || '/api/v1')
  const proxyTarget = env.VITE_API_PROXY_TARGET || env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

  return {
    plugins: [vue()],
    resolve: {
      // 优先解析 TypeScript 源文件，避免同目录历史编译产物 .js 抢先命中导致运行时代码滞后。
      extensions: ['.ts', '.tsx', '.mjs', '.js', '.vue', '.json'],
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port,
      proxy: {
        [apiPrefix]: {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})

/**
 * 规范化 API 前缀。
 *
 * 参数：
 *   prefix: 环境变量或默认值中的 API 前缀。
 *
 * 返回值：
 *   以 / 开头、末尾不带 / 的路径，便于 Vite proxy 精确匹配。
 */
function normalizeApiPrefix(prefix: string) {
  const value = prefix.trim() || '/api/v1'
  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`
  return withLeadingSlash.replace(/\/+$/, '') || '/api/v1'
}
