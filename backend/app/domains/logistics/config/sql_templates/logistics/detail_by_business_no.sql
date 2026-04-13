-- 业务编号明细模板
SELECT
    {{ contract_no }} AS contract_no,
    {{ task_id }} AS task_id,
    {{ source_scope }} AS source_scope
FROM dws_logistics_detail_union
WHERE 1 = 1;
