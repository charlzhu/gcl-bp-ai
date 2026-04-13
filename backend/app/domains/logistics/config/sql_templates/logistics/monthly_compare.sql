-- 物流跨时间窗口对比模板
SELECT
    {{ metric_type }} AS metric_type,
    {{ compare_dim }} AS compare_dim,
    {{ source_scope }} AS source_scope,
    {{ year_month_list }} AS year_month_list
FROM dws_logistics_monthly_metric
WHERE 1 = 1;
