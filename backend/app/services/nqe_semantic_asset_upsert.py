"""NQE 语义资产 upsert 服务 — 可复现版本。

使用方式:
    PYTHONPATH=. python backend/app/services/nqe_semantic_asset_upsert.py [--dry-run]

从 logistics_ai 中间库表结构和真实枚举值生成 nqe_* 语义资产。
幂等: 重复运行不会重复插入。
"""

from __future__ import annotations

import json, sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ============================================================
# SEED CONFIG — 可维护的种子配置
# ============================================================

DOMAINS = [
    ("logistics", "物流"),
    ("business_analysis", "产销存/经营分析"),
    ("plan_bom", "计划BOM"),
    ("power_prediction", "功率预测"),
]

# 维度配置: (domain, dimension_code, dimension_name, aliases, table_name, column_name)
DIMENSIONS = [
    ("logistics","biz_year","业务年度","年份","dws_logistics_detail_union","biz_year"),
    ("logistics","biz_month","业务月份","月份","dws_logistics_detail_union","biz_month"),
    ("logistics","origin_place","始发地","起始地,发货地","dws_logistics_detail_union","origin_place"),
    ("logistics","destination_place","目的地","到达地,收货地","dws_logistics_detail_union","destination_place"),
    ("logistics","carrier","承运商","物流公司,运输公司","dws_logistics_detail_union","logistics_company_name"),
    ("logistics","customer","客户","委托人,客户单位","dws_logistics_detail_union","customer_name"),
    ("business_analysis","business_year","业务年度","年份","dwd_ba_isp_monthly_fact","business_year"),
    ("business_analysis","business_month","业务月份","月份","dwd_ba_isp_monthly_fact","business_month"),
    ("business_analysis","base_name","基地","基地名称,工厂","dwd_ba_isp_monthly_fact","base_name"),
    ("business_analysis","metric_code","指标编码","指标ID","dwd_ba_isp_monthly_fact","metric_code"),
    ("business_analysis","metric_name","指标名称","指标","dwd_ba_isp_monthly_fact","metric_name"),
    ("business_analysis","unit","单位","计量单位","dwd_ba_isp_monthly_fact","unit"),
    ("plan_bom","order_no","订单号","单据号","plan_bom_header","order_no"),
    ("plan_bom","review_no","评审号","审批号","plan_bom_header","review_no"),
    ("plan_bom","order_name","订单名称","项目名","plan_bom_header","order_name"),
    ("plan_bom","material_category","物料类别","材料类型,类别","plan_bom_material_line","material_category"),
    ("plan_bom","sap_code","SAP编码","SAP物料号","plan_bom_material_line","sap_code"),
    ("plan_bom","version_no","版本号","版本","plan_bom_revision","version_no"),
    ("power_prediction","model_code","模型编码","型号,版型","plan_power_model_version","business_version_label"),
    ("power_prediction","supplier_name","供应商","电池供应商","plan_power_supplier_efficiency_distribution","supplier_name"),
    ("power_prediction","cell_size","电池尺寸","尺寸,规格","plan_power_model_version","business_version_label"),
    ("power_prediction","glass","玻璃配置","玻璃","plan_power_factor_option","option_label"),
    ("power_prediction","ribbon","焊带配置","焊带,汇流条,busbar","plan_power_factor_option","option_label"),
    ("power_prediction","cable","线缆配置","线缆","plan_power_factor_option","option_label"),
    ("power_prediction","power_bin","功率档位","功率区间","plan_power_power_bin","power_bin"),
]

# 指标配置: (domain, metric_code, metric_name, aliases, table_name, value_column, unit)
METRICS = [
    ("logistics","shipment_count","运输记录数","运输记录条数","dws_logistics_detail_union","shipment_count","条"),
    ("logistics","shipment_watt","发运功率","发运瓦数","dws_logistics_detail_union","shipment_watt","W"),
    ("logistics","shipment_trip_count","发运车次","车次数","dws_logistics_detail_union","shipment_trip_count","车次"),
    ("logistics","monthly_volume","月度运输量","月运输量","dws_logistics_monthly_metric","metric_value",""),
    ("business_analysis","production_actual_including_oem","实际产量（含委外）","产量,组件产量,实际产量,生产量,总产量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","production_actual_excluding_oem","实际产量（不含委外）","自产量,自产产量,不含委外产量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","shipment_volume","销量","发货量,销售量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","invoice_sales_volume","开票销量","发票销量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","ending_inventory_volume","期末库存","库存,存货","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","monthly_production","月度产量","月产量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","monthly_sales","月度销量","月销量","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("business_analysis","monthly_inventory","月度库存","月库存","dwd_ba_isp_monthly_fact","value_decimal","MW"),
    ("plan_bom","standard_usage","标准用量","标准消耗","plan_bom_material_line","standard_usage",""),
    ("plan_bom","production_loss","生产损耗","损耗率","plan_bom_material_line","production_loss","%"),
    ("plan_bom","material_qty","物料数量","用量,数量","plan_bom_material_line","quantity",""),
    ("power_prediction","center_power","中心功率","中心功率值","plan_power_model_version","","W"),
    ("power_prediction","std_dev","标准差","偏差","plan_power_model_version","",""),
    ("power_prediction","center_efficiency","中心效率","电池效率,转换效率","plan_power_model_version","","%"),
    ("power_prediction","power_bin_range","功率档位","功率区间","plan_power_power_bin","power_bin",""),
    ("power_prediction","supplier_efficiency","供应商效率","效率分布","plan_power_supplier_efficiency_distribution","efficiency","%"),
]

# value index 抽取配置: (domain, table_name, column_name, value_type)
VALUE_SOURCES = [
    ("logistics","dws_logistics_detail_union","origin_place","location"),
    ("logistics","dws_logistics_detail_union","biz_year","time"),
    ("logistics","dws_logistics_detail_union","biz_month","time"),
    ("logistics","dws_logistics_detail_union","logistics_company_name","entity"),
    ("logistics","dws_logistics_detail_union","customer_name","entity"),
    ("business_analysis","dwd_ba_isp_monthly_fact","metric_code","metric"),
    ("business_analysis","dwd_ba_isp_monthly_fact","metric_name","metric"),
    ("business_analysis","dwd_ba_isp_monthly_fact","base_name","location"),
    ("business_analysis","dwd_ba_isp_monthly_fact","business_year","time"),
    ("business_analysis","dwd_ba_isp_monthly_fact","business_month","time"),
    ("plan_bom","plan_bom_material_line","material_category","category"),
    ("plan_bom","plan_bom_material_line","sap_code","identifier"),
    ("plan_bom","plan_bom_material_line","order_no","identifier"),
    ("plan_bom","plan_bom_revision","version_no","version"),
    ("power_prediction","plan_power_supplier_efficiency_distribution","supplier_name","entity"),
    ("power_prediction","plan_power_factor_option","factor_key","config"),
    ("power_prediction","plan_power_factor_option","option_label","config"),
    ("power_prediction","plan_power_power_bin","power_bin","power"),
]

# few-shot SQL: (domain, question, sql, tables_json, metrics_json, dims_json, difficulty)
FEWSHOTS = [
    ("logistics","2024年运输记录数","SELECT COUNT(*) AS row_count FROM dws_logistics_detail_union WHERE biz_year = 2024",'["dws_logistics_detail_union"]','["shipment_count"]','["biz_year"]',"easy"),
    ("logistics","2023年各月运输量","SELECT biz_month, SUM(shipment_trip_count) AS total_trips FROM dws_logistics_detail_union WHERE biz_year = 2023 GROUP BY biz_month ORDER BY biz_month",'["dws_logistics_detail_union"]','["shipment_trip_count"]','["biz_month","biz_year"]',"easy"),
    ("logistics","各基地发运量","SELECT origin_place, SUM(shipment_watt) AS total_watt FROM dws_logistics_detail_union WHERE biz_year = 2024 GROUP BY origin_place ORDER BY total_watt DESC",'["dws_logistics_detail_union"]','["shipment_watt"]','["origin_place","biz_year"]',"easy"),
    ("logistics","各承运商运输量对比","SELECT logistics_company_name, COUNT(*) AS shipment_count, SUM(shipment_watt) AS total_watt FROM dws_logistics_detail_union WHERE biz_year = 2024 GROUP BY logistics_company_name ORDER BY total_watt DESC",'["dws_logistics_detail_union"]','["shipment_count","shipment_watt"]','["logistics_company_name","biz_year"]',"medium"),
    ("logistics","始发地发运明细","SELECT * FROM dws_logistics_detail_union WHERE origin_place = '合肥' LIMIT 100",'["dws_logistics_detail_union"]','[]','["origin_place"]',"medium"),
    ("business_analysis","2024年组件产量","SELECT SUM(value_decimal) AS total FROM dwd_ba_isp_monthly_fact WHERE business_year = 2024 AND metric_code = 'production_actual_including_oem' AND is_published_month = 1",'["dwd_ba_isp_monthly_fact"]','["production_actual_including_oem"]','["business_year","metric_code"]',"easy"),
    ("business_analysis","2023年各月销量","SELECT business_month, SUM(value_decimal) AS total FROM dwd_ba_isp_monthly_fact WHERE business_year = 2023 AND metric_code = 'shipment_volume' AND is_published_month = 1 GROUP BY business_month ORDER BY business_month",'["dwd_ba_isp_monthly_fact"]','["shipment_volume"]','["business_year","business_month","metric_code"]',"easy"),
    ("business_analysis","各基地产量对比","SELECT base_name, SUM(value_decimal) AS total FROM dwd_ba_isp_monthly_fact WHERE business_year = 2024 AND metric_code = 'production_actual_including_oem' AND is_published_month = 1 AND base_name IS NOT NULL GROUP BY base_name ORDER BY total DESC",'["dwd_ba_isp_monthly_fact"]','["production_actual_including_oem"]','["base_name","business_year","metric_code"]',"medium"),
    ("business_analysis","2024年末库存","SELECT SUM(value_decimal) AS ending_inventory FROM dwd_ba_isp_monthly_fact WHERE business_year = 2024 AND business_month = 12 AND metric_code = 'ending_inventory_volume' AND is_published_month = 1",'["dwd_ba_isp_monthly_fact"]','["ending_inventory_volume"]','["business_year","business_month","metric_code"]',"medium"),
    ("business_analysis","销量月度趋势","SELECT business_month, SUM(value_decimal) AS monthly_sales FROM dwd_ba_isp_monthly_fact WHERE business_year = 2024 AND metric_code = 'shipment_volume' AND is_published_month = 1 GROUP BY business_month ORDER BY business_month",'["dwd_ba_isp_monthly_fact"]','["shipment_volume"]','["business_year","business_month","metric_code"]',"easy"),
    ("plan_bom","订单BOM明细","SELECT order_no, material_name, sap_code, material_category, standard_usage, unit FROM plan_bom_material_line WHERE order_no = ? ORDER BY line_no",'["plan_bom_material_line"]','[]','["order_no"]',"easy"),
    ("plan_bom","SAP编码的BOM物料","SELECT order_no, material_name, standard_usage, unit FROM plan_bom_material_line WHERE sap_code = ? LIMIT 100",'["plan_bom_material_line"]','[]','["sap_code"]',"easy"),
    ("plan_bom","glass类别的物料","SELECT material_name, sap_code, standard_usage, unit FROM plan_bom_material_line WHERE material_category = 'glass' LIMIT 100",'["plan_bom_material_line"]','[]','["material_category"]',"easy"),
    ("plan_bom","BOM订单列表","SELECT order_no, review_no, order_name FROM plan_bom_header ORDER BY order_no DESC LIMIT 20",'["plan_bom_header"]','[]','[]',"easy"),
    ("plan_bom","按物料类别统计","SELECT material_category, COUNT(*) AS cnt, SUM(standard_usage) AS total_usage FROM plan_bom_material_line GROUP BY material_category ORDER BY cnt DESC",'["plan_bom_material_line"]','["standard_usage"]','["material_category"]',"medium"),
    ("power_prediction","功率模型版本","SELECT business_version_label FROM plan_power_model_version",'["plan_power_model_version"]','[]','[]',"easy"),
    ("power_prediction","供应商效率分布","SELECT supplier_name, efficiency FROM plan_power_supplier_efficiency_distribution ORDER BY efficiency DESC",'["plan_power_supplier_efficiency_distribution"]','[]','["supplier_name"]',"easy"),
    ("power_prediction","功率档位查询","SELECT power_bin, bin_order FROM plan_power_power_bin ORDER BY bin_order",'["plan_power_power_bin"]','[]','[]',"easy"),
    ("power_prediction","因子选项","SELECT factor_key, option_label, effect_value FROM plan_power_factor_option WHERE factor_key = 'glass' LIMIT 50",'["plan_power_factor_option"]','[]','["factor_key"]',"medium"),
    ("power_prediction","基准因子","SELECT * FROM plan_power_benchmark_factor",'["plan_power_benchmark_factor"]','[]','[]',"easy"),
]


# ============================================================
# UPSERT LOGIC
# ============================================================

class NqeSemanticAssetUpsert:
    """语义资产 upsert 服务。幂等，支持 dry-run。"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._db = None

    def _get_db(self):
        if self._db is None:
            from backend.app.db.session import SessionLocal
            self._db = SessionLocal()
        return self._db

    def run(self) -> dict[str, int]:
        db = self._get_db()
        from sqlalchemy import text

        counts: dict[str, int] = {}

        def _count(table: str) -> int:
            return db.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]

        if self.dry_run:
            print("[DRY-RUN] Would upsert nqe_* tables")
            return {t: _count(t) for t in ['nqe_domain','nqe_table_info','nqe_column_info','nqe_metric_info','nqe_dimension_info','nqe_value_index','nqe_fewshot_sql']}

        # 1. Domains
        db.execute(text("DELETE FROM nqe_domain"))
        for code, name in DOMAINS:
            db.execute(text("INSERT IGNORE INTO nqe_domain (domain_code, domain_name) VALUES (:c,:n)"), {'c':code,'n':name})
        db.commit()
        counts['nqe_domain'] = _count('nqe_domain')

        # 2. Table info from real tables
        db.execute(text("DELETE FROM nqe_table_info"))
        for (t,) in db.execute(text("SHOW TABLES")).fetchall():
            if t.startswith('alembic') or t.startswith('nqe_'): continue
            domain = self._classify_domain(t)
            if not domain: continue
            db.execute(text("INSERT INTO nqe_table_info (domain_code, table_name, is_queryable) VALUES (:d,:t,1)"), {'d':domain,'t':t})
        db.commit()
        counts['nqe_table_info'] = _count('nqe_table_info')

        # 3. Column info
        db.execute(text("DELETE FROM nqe_column_info"))
        for domain, tname in db.execute(text("SELECT domain_code, table_name FROM nqe_table_info")).fetchall():
            try:
                for row in db.execute(text(f"DESCRIBE `{tname}`")).fetchall():
                    cn, ct = row[0], str(row[1])
                    db.execute(text("INSERT INTO nqe_column_info (domain_code, table_name, column_name, data_type) VALUES (:d,:t,:c,:dt)"), {'d':domain,'t':tname,'c':cn,'dt':ct})
            except: pass
        db.commit()
        counts['nqe_column_info'] = _count('nqe_column_info')

        # 4. Metrics
        db.execute(text("DELETE FROM nqe_metric_info"))
        for domain, code, name, aliases, table, val_col, unit in METRICS:
            db.execute(text("INSERT INTO nqe_metric_info (domain_code, metric_code, metric_name, aliases, table_name, value_column, unit) VALUES (:d,:c,:n,:a,:t,:vc,:u)"),
                      {'d':domain,'c':code,'n':name,'a':aliases,'t':table,'vc':val_col,'u':unit})
        db.commit()
        counts['nqe_metric_info'] = _count('nqe_metric_info')

        # 5. Dimensions
        db.execute(text("DELETE FROM nqe_dimension_info"))
        for domain, code, name, aliases, table, column in DIMENSIONS:
            db.execute(text("INSERT INTO nqe_dimension_info (domain_code, dimension_code, dimension_name, aliases, table_name, column_name, is_active) VALUES (:d,:c,:n,:a,:t,:col,1)"),
                      {'d':domain,'c':code,'n':name,'a':aliases,'t':table,'col':column})
        db.commit()
        counts['nqe_dimension_info'] = _count('nqe_dimension_info')

        # 6. Value index (from real DB — max 200 per column)
        db.execute(text("DELETE FROM nqe_value_index"))
        for domain, table, column, vtype in VALUE_SOURCES:
            try:
                rows = db.execute(text(f"SELECT DISTINCT `{column}` FROM `{table}` WHERE `{column}` IS NOT NULL LIMIT 200"))
                for (val,) in rows.fetchall():
                    db.execute(text("INSERT IGNORE INTO nqe_value_index (domain_code, table_name, column_name, raw_value, value_type) VALUES (:d,:t,:c,:v,:vt)"),
                              {'d':domain,'t':table,'c':column,'v':str(val),'vt':vtype})
            except Exception as e:
                print(f"  [SKIP] {table}.{column}: {e}")
        db.commit()
        counts['nqe_value_index'] = _count('nqe_value_index')

        # 7. Few-shot SQL
        db.execute(text("DELETE FROM nqe_fewshot_sql"))
        for domain, q, sql, tables_json, metrics_json, dims_json, diff in FEWSHOTS:
            db.execute(text("INSERT INTO nqe_fewshot_sql (domain_code, question, `sql`, `tables`, metrics, dimensions, difficulty, is_active) VALUES (:d,:q,:s,:t,:m,:dim,:df,1)"),
                      {'d':domain,'q':q,'s':sql,'t':tables_json,'m':metrics_json,'dim':dims_json,'df':diff})
        db.commit()
        counts['nqe_fewshot_sql'] = _count('nqe_fewshot_sql')

        return counts

    def _classify_domain(self, table_name: str) -> str | None:
        if table_name.startswith('plan_bom'): return 'plan_bom'
        if table_name.startswith('plan_power'): return 'power_prediction'
        if any(table_name.startswith(p) for p in ['dwd_ba','dim_ba','ods_ba']): return 'business_analysis'
        if any(table_name.startswith(p) for p in ['ods_logistic','dwd_logistic','dws_logistic','dm_logistic','sys_','ods_hist']): return 'logistics'
        return None


# ============================================================
# CLI entry
# ============================================================

if __name__ == "__main__":
    dry = '--dry-run' in sys.argv
    upsert = NqeSemanticAssetUpsert(dry_run=dry)
    print(f"{'[DRY-RUN]' if dry else '[REAL]'} Running upsert...")
    result = upsert.run()
    print(f"\n=== RESULTS ===")
    for table, cnt in result.items():
        # show per-domain distribution
        db = upsert._get_db()
        from sqlalchemy import text as t2
        by = {}
        try:
            r = db.execute(t2(f"SELECT domain_code, COUNT(*) FROM {table} GROUP BY domain_code"))
            by = dict(r.fetchall())
        except: pass
        print(f"  {table}: {cnt} rows {by}")
    db.close() if upsert._db else None
