-- 物流月度指标总量模板
SELECT
    {{ metric_type }} AS metric_type,
    {{ group_by }} AS group_by,
    {{ source_scope }} AS source_scope,
    {{ start_date }} AS start_date,
    {{ end_date }} AS end_date,
    {{ year_month_list }} AS year_month_list
FROM dws_logistics_monthly_metric
WHERE 1 = 1;
