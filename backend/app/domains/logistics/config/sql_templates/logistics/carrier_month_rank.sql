-- 物流公司月度排名模板
SELECT
    {{ metric_type }} AS metric_type,
    {{ logistics_company_name }} AS logistics_company_name,
    {{ source_scope }} AS source_scope,
    {{ year_month_list }} AS year_month_list
FROM dws_logistics_monthly_metric
WHERE 1 = 1;
