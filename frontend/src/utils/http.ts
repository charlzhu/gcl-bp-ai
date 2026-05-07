import axios from 'axios'
import { ElMessage } from 'element-plus'

const API_PREFIX = normalizeApiPrefix(import.meta.env.VITE_API_PREFIX || '/api/v1')
const DIRECT_API_BASE_URL = (import.meta.env.VITE_DIRECT_API_BASE_URL || '').trim()

/**
 * 规范化 API 前缀。
 *
 * 参数：
 *   prefix: 环境变量中配置的后端统一 API 前缀。
 *
 * 返回值：
 *   以 / 开头、末尾不带 / 的 API 前缀。
 *
 * 业务逻辑：
 *   统一用相对地址访问后端，避免公网/非安全上下文页面直接请求内网 IP，触发 Chrome
 *   Private Network Access 风险提示或后续阻断。
 */
function normalizeApiPrefix(prefix: string) {
  const value = prefix.trim() || '/api/v1'
  const withLeadingSlash = value.startsWith('/') ? value : `/${value}`
  return withLeadingSlash.replace(/\/+$/, '') || '/api/v1'
}

/**
 * 构造浏览器侧 Axios baseURL。
 *
 * 返回值：
 *   默认返回相对路径 `/api/v1`，由同源网关、Nginx 或 Vite dev proxy 转发到后端。
 *
 * 重要业务逻辑：
 *   Chrome 已逐步禁止非安全上下文访问私有网络子资源。生产或演示环境如果把前端部署在
 *   `http://公网域名`，再从浏览器直连 `http://127.0.0.1`、`http://192.168.*`、`http://10.*`
 *   等后端地址，就会出现用户反馈的 Private Network Access 告警。这里默认不再使用
 *   `VITE_API_BASE_URL` 拼接绝对地址，而是使用同源相对路径，彻底避免浏览器跨网络空间直连。
 */
function resolveBrowserApiBaseURL() {
  if (!DIRECT_API_BASE_URL) return API_PREFIX
  return `${DIRECT_API_BASE_URL.replace(/\/+$/, '')}${API_PREFIX}`
}

/**
 * Axios 实例。
 * 说明：
 * 1. 默认使用同源相对 API 地址；
 * 2. 本地开发由 Vite proxy 转发，生产由部署网关反向代理；
 * 3. 后续如果要接 token，可以在这里统一加拦截器。
 */
export const http = axios.create({
  baseURL: resolveBrowserApiBaseURL(),
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error?.response?.data?.message ||
      error?.response?.data?.detail ||
      error?.message ||
      '请求失败，请稍后重试'
    ElMessage.error(message)
    return Promise.reject(error)
  },
)
