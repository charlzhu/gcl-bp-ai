import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

/**
 * Vite 配置
 * 说明：
 * 1. 支持通过 .env.local 配置本地 API 地址；
 * 2. 配置了 @ 路径别名，便于后续模块化开发；
 * 3. 默认开发端口可通过环境变量 VITE_PORT 覆盖。
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = Number(env.VITE_PORT || 5173)

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port,
    },
  }
})
