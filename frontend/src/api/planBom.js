import { http } from '@/utils/http';
/**
 * 调用计划 BOM 明细查询接口。
 * 说明：
 * 统一透传后端 detail 查询请求，页面不自行推断候选和版本。
 */
export async function fetchPlanBomDetailQuery(payload) {
    const resp = await http.post('/plan-bom/query/detail', payload);
    return resp.data;
}
/**
 * 调用计划 BOM 自然语言问答接口。
 */
export async function askPlanBomQuestion(payload) {
    const resp = await http.post('/plan-bom/qa/ask', payload);
    return resp.data;
}
/**
 * 上传计划 BOM Excel 文件。
 * 说明：
 * 1. 默认参数保持原有试运行链路；
 * 2. 页面可透传 source / remark，方便业务人员理解上传来源；
 * 3. 不在前端解析 Excel 内容，事实解析仍交给后端真实上传接口。
 */
export async function uploadPlanBomExcel(file, options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('business_type', options.business_type || 'plan_bom');
    formData.append('source', options.source || 'manual_upload');
    formData.append('overwrite', String(options.overwrite ?? true));
    if (options.remark) {
        formData.append('remark', options.remark);
    }
    const resp = await http.post('/plan-bom/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return resp.data;
}
