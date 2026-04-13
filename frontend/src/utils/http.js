import axios from 'axios';
import { ElMessage } from 'element-plus';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_PREFIX = import.meta.env.VITE_API_PREFIX || '/api/v1';
/**
 * Axios 实例。
 * 说明：
 * 1. 统一拼接后端 API 前缀；
 * 2. 统一处理错误消息；
 * 3. 后续如果要接 token，可以在这里统一加拦截器。
 */
export const http = axios.create({
    baseURL: `${API_BASE_URL}${API_PREFIX}`,
    timeout: 30000,
});
http.interceptors.response.use((response) => response, (error) => {
    const message = error?.response?.data?.message ||
        error?.response?.data?.detail ||
        error?.message ||
        '请求失败，请稍后重试';
    ElMessage.error(message);
    return Promise.reject(error);
});
