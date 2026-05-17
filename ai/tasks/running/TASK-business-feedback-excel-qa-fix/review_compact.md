# Compact independent review input

## Static scan
```text
# Static scan on task patch added lines
## hardcoded secrets
## shell injection
## dangerous eval/exec
## unsafe deserialization
## SQL f-string heuristic

```

## Verification summary
```text
## focused
- exit: `0`
- key: `14 passed in 1.58s`
## excel_full_reproduction
- exit: `0`
- key: `{"questions": 72, "ok": 72, "errors": 0}`
## compile
- exit: `0`
- key: `see tail`
## full_business_acceptance
- exit: `0`
- key: `185 passed, 2 warnings in 37.78s`
## frontend_build
- exit: `0`
- key: `✓ built in 5.76s | vite chunk-size warning only`
## api_stream_smoke
- exit: `0`
- key: `"event": "done"`
## browser_smoke
- exit: `0` (manual browser tool verification)
- evidence: smart-chat page accepted `25年物流公司发货量分别是多少？`, routed to 物流数据, displayed `已解答`, chart/table, 20 detail rows, no `请求出错`.
```

## Diff stat
```text
 .../logistics/repositories/data_qa_repository.py   | 162 ++++++++++++++++++---
 .../domains/logistics/services/data_qa_planner.py  | 103 +++++++++++--
 .../domains/logistics/services/data_qa_service.py  |  55 ++++++-
 .../app/domains/plan_bom/services/qa_service.py    |  40 ++++-
 4 files changed, 320 insertions(+), 40 deletions(-)

new file: tests/business_acceptance/test_business_feedback_excel_qa_regression.py
```

## Repository snippets: carrier KPI, unit fee monthly, city rank

```python
564:     def hist_carrier_kpi_by_year(self, *, year: int, region_name: str | None = None) -> dict[str, Any]:
565:         """历史年度承运商 KPI 统计。
566: 
567:         参数：
568:             year: 业务年份；
569:             region_name: 可选区域过滤，例如“西北”。为空时统计全年全区域。
570: 
571:         返回：
572:             1. 各承运商的发运量 MW；
573:             2. 发运量占比；
574:             3. 运费总额。
575: 
576:         说明：
577:             1. 发运量默认按瓦数口径，折算为 MW；
578:             2. 占比基于当前查询范围内全部承运商的总发运量；
579:             3. 统一兼容“承运商 / 物流公司 / 物流供应商”问法；
580:             4. 区域过滤必须下推到总量分母和明细分子，避免区域题退回全国口径。
581:         """
582: 
583:         params: dict[str, Any] = {"year": year}
584:         filters = [
585:             "biz_year = :year",
586:             "logistics_company_name IS NOT NULL",
587:             "TRIM(logistics_company_name) <> ''",
588:         ]
589:         if region_name:
590:             filters.append("region_name = :region_name")
591:             params["region_name"] = region_name
592:         where_clause = " AND ".join(filters)
593: 
594:         total_shipment_mw = self.db.execute(
595:             text(
596:                 f"""
597:                 SELECT ROUND(SUM(actual_watt) / 1000000, 3)
598:                 FROM dwd_logistics_hist_shipment_detail
599:                 WHERE {where_clause}
600:                 """
601:             ),
602:             params,
603:         ).scalar()
604:         rows = self.db.execute(
605:             text(
606:                 f"""
607:                 SELECT
608:                     logistics_company_name AS carrier_name,
609:                     ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
610:                     ROUND(
611:                         100 * SUM(actual_watt) / NULLIF((
612:                             SELECT SUM(actual_watt)
613:                             FROM dwd_logistics_hist_shipment_detail
614:                             WHERE {where_clause}
615:                         ), 0),
616:                         2
617:                     ) AS shipment_share_pct,
618:                     ROUND(SUM(total_fee), 0) AS total_fee
619:                 FROM dwd_logistics_hist_shipment_detail
620:                 WHERE {where_clause}
621:                 GROUP BY logistics_company_name
622:                 ORDER BY shipment_mw DESC, total_fee DESC, logistics_company_name ASC
623:                 """
624:             ),
625:             params,
626:         ).mappings().all()
627:         return {
628:             "total_shipment_mw": total_shipment_mw,
629:             "items": [dict(row) for row in rows],
630:         }
631: 
632:     def hist_mw_summary(
633:         self,
634:         *,
635:         year: int,
636:         months: list[int] | None = None,
637:         customer_name: str | None = None,
638:         region_name: str | None = None,
639:         origin_place: str | None = None,
640:         carrier_name: str | None = None,
641:         transport_mode: str | None = None,
642:     ) -> dict[str, Any]:
643:         """历史 MW 汇总。
644: 
645:         说明：
646:             1. 统一承接客户、区域、始发地、承运商等单值过滤；
647:             2. 发运量固定按 actual_watt 汇总后除以 1,000,000；
648:             3. 该方法只返回单值汇总，不负责分组拆分。
649:         """
650:         filters = ["biz_year = :year"]
651:         params: dict[str, Any] = {"year": year}
652:         if months:
653:             month_placeholders = ", ".join(str(int(month)) for month in months)
654:             filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
655:         if customer_name:
656:             filters.append("customer_name LIKE :customer_name")
657:             # 客户简称可能出现在客户全称中间，例如“创维”对应“南京创维光伏科技有限公司”。
658:             # 这里使用包含匹配，仍只作用于已由 planner 抽取出的客户槽位。
659:             params["customer_name"] = f"%{customer_name}%"
660:         if region_name:
661:             filters.append("region_name = :region_name")
662:             params["region_name"] = region_name
663:         if origin_place:
664:             filters.append("origin_place = :origin_place")
665:             params["origin_place"] = origin_place
666:         if carrier_name:
667:             filters.append("logistics_company_name LIKE :carrier_name")
668:             params["carrier_name"] = f"%{carrier_name}%"
669:         if transport_mode:
670:             if transport_mode == "公路":
```

```python
1315:     def hist_unit_fee_per_watt(
1316:         self,
1317:         *,
1318:         year: int,
1319:         province: str | None = None,
1320:         months: list[int] | None = None,
1321:         include_extra_fee: bool = False,
1322:         transport_mode: str | None = None,
1323:         carrier_name: str | None = None,
1324:         monthly_breakdown: bool = False,
1325:     ) -> dict[str, Any] | list[dict[str, Any]]:
1326:         """历史单瓦运输成本。
1327: 
1328:         参数：
1329:             year: 统计年份。
1330:             province: 可选目的省份过滤。
1331:             months: 可选月份过滤。
1332:             include_extra_fee: 是否把 extra_fee 一并纳入分子。
1333:             transport_mode: 可选运输方式过滤，公路/铁路会合并同义写法。
1334:             carrier_name: 可选承运商简称，按物流公司名称模糊匹配。
1335:             monthly_breakdown: 是否按业务月份分组返回月度明细。
1336: 
1337:         说明：
1338:             1. `单瓦价` 默认按 total_fee / actual_watt；
1339:             2. 当业务明确要求“(运费+额外费用)/总W数”时，再纳入 extra_fee；
1340:             3. 承运商过滤只用于已通过 planner 校验的历史承运商别名题族；
1341:             4. 用户要求 1-12 月/按月时，仓储层直接按月份分组，避免服务层拿年度总计伪造成月表。
1342:         """
1343:         filters = ["biz_year = :year", "actual_watt IS NOT NULL", "actual_watt <> 0"]
1344:         params: dict[str, Any] = {"year": year}
1345:         if province:
1346:             filters.append("province = :province")
1347:             params["province"] = province
1348:         if months:
1349:             month_placeholders = ", ".join(str(int(month)) for month in months)
1350:             filters.append(f"MONTH(biz_date) IN ({month_placeholders})")
1351:         if transport_mode:
1352:             mode_filter, mode_params = self._transport_mode_filter_sql(transport_mode)
1353:             filters.append(mode_filter)
1354:             params.update(mode_params)
1355:         if carrier_name:
1356:             filters.append("logistics_company_name LIKE :carrier_name")
1357:             params["carrier_name"] = f"%{carrier_name}%"
1358:         numerator_sql = "SUM(total_fee)" if not include_extra_fee else "SUM(total_fee) + SUM(COALESCE(extra_fee, 0))"
1359:         where_sql = " AND ".join(filters)
1360:         if monthly_breakdown:
1361:             rows = self.db.execute(
1362:                 text(
1363:                     f"""
1364:                     SELECT
1365:                         DATE_FORMAT(biz_date, '%Y-%m') AS biz_month,
1366:                         ROUND({numerator_sql}, 0) AS total_fee_amount,
1367:                         ROUND(SUM(COALESCE(extra_fee, 0)), 0) AS extra_fee_amount,
1368:                         ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
1369:                         ROUND(({numerator_sql}) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt
1370:                     FROM dwd_logistics_hist_shipment_detail
1371:                     WHERE {where_sql}
1372:                       AND biz_date IS NOT NULL
1373:                     GROUP BY DATE_FORMAT(biz_date, '%Y-%m')
1374:                     ORDER BY biz_month ASC
1375:                     """
1376:                 ),
1377:                 params,
1378:             ).mappings().all()
1379:             return [dict(row) for row in rows]
1380:         row = self.db.execute(
1381:             text(
1382:                 f"""
1383:                 SELECT
1384:                     ROUND({numerator_sql}, 0) AS total_fee_amount,
1385:                     ROUND(SUM(COALESCE(extra_fee, 0)), 0) AS extra_fee_amount,
1386:                     ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw,
1387:                     ROUND(({numerator_sql}) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt
1388:                 FROM dwd_logistics_hist_shipment_detail
1389:                 WHERE {where_sql}
1390:                 """
1391:             ),
1392:             params,
1393:         ).mappings().first()
1394:         return dict(row or {})
1395: 
1396:     def hist_city_mw_rank(
1397:         self,
1398:         *,
1399:         year: int,
1400:         top_n: int,
1401:         region_name: str | None = None,
1402:         province: str | None = None,
1403:     ) -> dict[str, Any]:
1404:         """历史城市发运量 TopN 排名。
1405: 
1406:         参数：
1407:             year: 统计年份。
1408:             top_n: 返回城市数量上限。
1409:             region_name: 可选大区过滤，例如“华东”。
1410:             province: 可选省份过滤，例如“安徽”。
1411: 
1412:         返回：
1413:             包含统计范围、筛选后城市发运量总和和城市排名明细。
1414: 
1415:         说明：
1416:             1. 城市发运量按 actual_watt 汇总后折算为 MW；
1417:             2. 区域/省份过滤先下推，再按城市分组排序，防止 TopN 使用全国口径；
1418:             3. 仅统计城市字段非空的历史台账记录。
1419:         """
1420:         filters = [
1421:             "biz_year = :year",
1422:             "city IS NOT NULL",
1423:             "TRIM(city) <> ''",
1424:         ]
1425:         params: dict[str, Any] = {"year": year, "limit_value": int(top_n)}
1426:         scope_parts = [f"{year}年"]
1427:         if region_name:
1428:             filters.append("region_name = :region_name")
1429:             params["region_name"] = region_name
1430:             scope_parts.append(f"{region_name}区域")
1431:         if province:
1432:             filters.append("province = :province")
1433:             params["province"] = province
1434:             scope_parts.append(f"{province}省")
1435:         where_sql = " AND ".join(filters)
1436:         rows = self.db.execute(
1437:             text(
1438:                 f"""
1439:                 SELECT
1440:                     city,
1441:                     ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
1442:                 FROM dwd_logistics_hist_shipment_detail
1443:                 WHERE {where_sql}
1444:                 GROUP BY city
1445:                 ORDER BY shipment_mw DESC, city ASC
1446:                 LIMIT :limit_value
1447:                 """
1448:             ),
1449:             params,
1450:         ).mappings().all()
1451:         return {
1452:             "total_shipment_mw": round(sum(float(row["shipment_mw"] or 0) for row in rows), 3),
1453:             "items": [dict(row) for row in rows],
1454:             "scope_label": "".join(scope_parts),
1455:         }
1456: 
1457:     def hist_route_pricing_analysis(
1458:         self,
1459:         *,
1460:         years: list[int],
```

```python
1798:                         ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
1799:                     FROM dwd_logistics_hist_shipment_detail
1800:                     WHERE biz_year = :year
1801:                       AND logistics_company_name IS NOT NULL
1802:                       AND TRIM(logistics_company_name) <> ''
1803:                     GROUP BY logistics_company_name
1804:                     ORDER BY total_fee DESC, shipment_mw DESC, carrier_name ASC
1805:                     LIMIT :limit_value
1806:                     """
1807:                 ),
1808:                 {"year": year, "limit_value": top_n},
1809:             ).mappings().all()
1810:             return [dict(row) for row in rows]
1811: 
1812:         rows = self.db.execute(
1813:             text(
1814:                 """
1815:                 SELECT
1816:                     logistics_company_name AS carrier_name,
1817:                     ROUND(SUM(total_fee) / NULLIF(SUM(actual_watt), 0), 8) AS unit_fee_per_watt,
1818:                     ROUND(SUM(total_fee), 0) AS total_fee,
1819:                     ROUND(SUM(actual_watt) / 1000000, 3) AS shipment_mw
1820:                 FROM dwd_logistics_hist_shipment_detail
1821:                 WHERE biz_year = :year
1822:                   AND logistics_company_name IS NOT NULL
1823:                   AND TRIM(logistics_company_name) <> ''
1824:                   AND actual_watt IS NOT NULL
1825:                   AND actual_watt <> 0
1826:                 GROUP BY logistics_company_name
1827:                 ORDER BY unit_fee_per_watt DESC, total_fee DESC, carrier_name ASC
1828:                 LIMIT :limit_value
1829:                 """
1830:             ),
1831:             {"year": year, "limit_value": top_n},
1832:         ).mappings().all()
1833:         return [dict(row) for row in rows]
1834: 
1835:     def hist_trip_count_by_region(self, *, year: int, region_name: str) -> dict[str, Any]:
1836:         """历史总车次。"""
1837:         total = self.db.execute(
1838:             text(
1839:                 """
1840:                 SELECT ROUND(SUM(shipment_trip_count), 0)
1841:                 FROM dwd_logistics_hist_shipment_detail
1842:                 WHERE biz_year = :year AND region_name = :region_name
1843:                 """
1844:             ),
1845:             {"year": year, "region_name": region_name},
1846:         ).scalar()
1847:         return {"shipment_trip_count": total}
1848: 
1849:     def hist_quantity_by_region(self, *, region_name: str, year: int | None = None, transport_mode: str | None = None) -> dict[str, Any]:
1850:         """历史总发运件数。
1851: 
1852:         参数：
1853:             region_name: 区域名称。
1854:             year: 可选年份过滤。
1855:             transport_mode: 可选运输方式过滤，公路/汽运、铁路/铁运按同义口径合并。
1856: 
1857:         返回值：包含 `shipment_count` 的汇总字典。
1858:         """
1859:         filters = ["region_name = :region_name"]
1860:         params: dict[str, Any] = {"region_name": region_name}
1861:         # 用户明确给出年份时，件数口径必须按该年份过滤；未给年份时保留历史累计兼容口径。
1862:         if year:
1863:             filters.append("biz_year = :year")
1864:             params["year"] = year
1865:         if transport_mode:
1866:             mode_filter, mode_params = self._transport_mode_filter_sql(transport_mode)
1867:             filters.append(mode_filter)
1868:             params.update(mode_params)
1869:         where_sql = " AND ".join(filters)
1870:         total = self.db.execute(
1871:             text(
1872:                 f"""
1873:                 SELECT ROUND(SUM(actual_qty), 0)
1874:                 FROM dwd_logistics_hist_shipment_detail
1875:                 WHERE {where_sql}
```

## Service snippets: calls and business text

```python
1017:         if plan.query_key == "hist_carrier_kpi_by_year":
1018:             data = self.repository.hist_carrier_kpi_by_year(
1019:                 year=filters["year"],
1020:                 region_name=filters.get("region_name"),
1021:             )
1022:             view_mode = filters.get("view_mode", "full_kpi")
1023:             region_text = f"{filters['region_name']}区域" if filters.get("region_name") else ""
1024:             if view_mode == "fee_only":
1025:                 summary = f"{filters['year']}年{region_text}各物流承运商年度运输费用已汇总返回。"
1026:             else:
1027:                 summary = (
1028:                     f"{filters['year']}年{region_text}各物流承运商的发运量、占比和运费总额已汇总返回。"
1029:                 )
1030:             return self._build_result(
1031:                 answer_summary=summary,
1032:                 plan=plan,
1033:                 table_columns=["carrier_name", "shipment_mw", "shipment_share_pct", "total_fee"],
1034:                 table_rows=data["items"],
1035:                 calculation_logic=[
1036:                     "承运量默认按历史 actual_watt 汇总后折算为 MW。",
1037:                     "承运量占比 = 当前承运商 shipment_mw / 当前查询范围内全部承运商 shipment_mw。",
1038:                     "运费总额按历史 total_fee 汇总。",
1039:                 ],
1040:                 data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
1041:                 warnings=warnings,
1042:             )
1043: 
```

```python
1251:         if plan.query_key == "hist_unit_fee_per_watt":
1252:             data = self.repository.hist_unit_fee_per_watt(
1253:                 year=filters["year"],
1254:                 province=filters.get("province"),
1255:                 months=filters.get("months"),
1256:                 include_extra_fee=filters.get("include_extra_fee", False),
1257:                 transport_mode=filters.get("transport_mode"),
1258:                 carrier_name=filters.get("carrier_name"),
1259:                 monthly_breakdown=bool(filters.get("monthly_breakdown")),
1260:             )
1261:             scope_label = filters.get("province") or filters.get("transport_mode") or filters.get("carrier_name") or ""
1262:             if filters.get("monthly_breakdown"):
1263:                 # 用户明确要求 1-12 月或按月展示时，保留月份粒度，避免服务层把已下推的 monthly_breakdown 压平成总计行。
1264:                 monthly_rows = data if isinstance(data, list) else data.get("monthly_rows", [])
1265:                 summary = f"{filters['year']}年{scope_label}按月单瓦运输成本已返回。"
1266:                 return self._build_result(
1267:                     answer_summary=summary,
1268:                     plan=plan,
1269:                     table_columns=["biz_month", "total_fee_amount", "extra_fee_amount", "shipment_mw", "unit_fee_per_watt"],
1270:                     table_rows=monthly_rows,
1271:                     calculation_logic=[
1272:                         "月度单瓦价默认按当月 total_fee / actual_watt。",
1273:                         "当问题明确要求“运费+额外费用”时，再把当月 extra_fee 一并纳入分子。",
1274:                         "月份粒度按历史台账 biz_date 对应 YYYY-MM 返回。",
1275:                     ],
1276:                     data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
1277:                     warnings=warnings,
1278:                 )
1279:             summary = (
1280:                 f"{filters['year']}年{scope_label}单瓦运输成本为"
1281:                 f"{data.get('unit_fee_per_watt') or 0}元/瓦。"
1282:             )
1283:             return self._build_result(
1284:                 answer_summary=summary,
1285:                 plan=plan,
1286:                 table_columns=["unit_fee_per_watt", "total_fee_amount", "extra_fee_amount", "shipment_mw"],
1287:                 table_rows=[data],
1288:                 calculation_logic=[
1289:                     "单瓦价默认按 total_fee / actual_watt。",
1290:                     "当问题明确要求“运费+额外费用”时，再把 extra_fee 一并纳入分子。",
1291:                 ],
1292:                 data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
1293:                 warnings=warnings,
1294:             )
1295: 
1296:         if plan.query_key == "hist_city_mw_rank":
1297:             data = self.repository.hist_city_mw_rank(
1298:                 year=filters["year"],
1299:                 top_n=int(filters.get("top_n") or plan.limit or 10),
1300:                 region_name=filters.get("region_name"),
1301:                 province=filters.get("province"),
1302:             )
1303:             scope_label = data.get("scope_label") or f"{filters['year']}年"
1304:             summary = f"{scope_label}城市发运量前{int(filters.get('top_n') or plan.limit or 10)}名已按 MW 返回。"
1305:             return self._build_result(
1306:                 answer_summary=summary,
1307:                 plan=plan,
1308:                 table_columns=["city", "shipment_mw"],
1309:                 table_rows=data.get("items") or [],
1310:                 calculation_logic=[
1311:                     "历史城市发运量按 actual_watt 汇总后除以 1,000,000 折算为 MW。",
1312:                     "当问题给出区域或省份时，先下推对应过滤条件，再按城市分组排序。",
1313:                 ],
1314:                 data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
1315:                 warnings=warnings,
1316:             )
```

```python
1560:         if plan.query_key == "hist_customer_mw":
1561:             data = self.repository.hist_customer_mw(
1562:                 year=filters.get("year"),
1563:                 customer_name=filters["customer_name"],
1564:                 months=filters.get("months"),
1565:             )
1566:             matched_names = data.get("matched_customer_names", [])
1567:             if len(matched_names) > 1:
1568:                 warnings.append(f"当前按客户名前缀归并，命中了 {len(matched_names)} 个客户名变体。")
1569:             summary = f"{data['scope_label']}{filters['customer_name']}总发运量为{data['shipment_mw'] or 0}MW。"
1570:             return self._build_result(
1571:                 answer_summary=summary,
1572:                 plan=plan,
1573:                 table_columns=["shipment_mw"],
1574:                 table_rows=[data],
1575:                 calculation_logic=[
1576:                     "历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。",
1577:                     "客户名按业务问法做前缀归并，以兼容同一项目的名称变体。",
1578:                     "未给年份时默认按 2023–2025 历史台账累计统计。",
1579:                 ],
1580:                 data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
1581:                 warnings=warnings,
1582:             )
```

## Plan BOM ambiguity snippet

```python
430:         else:
431:             resolution = self.power_config_resolver.resolve_explicit_configuration(
432:                 model_code=nlu.slots.get("model"),
433:                 configuration=explicit_configuration,
434:             )
435:         resolution_payload = resolution.to_dict()
436:         if resolution.status in {CANDIDATE_REQUIRED_STATUS, PARTIAL_STATUS}:
437:             slot_name = "candidate" if resolution.status == CANDIDATE_REQUIRED_STATUS else "power_configuration"
438:             nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), slot_name]))
439:             return self._with_presentation(
440:                 PlanBomQaResponse(
441:                     question=question,
442:                     classification="B",
443:                     status=PlanBomQaStatus(
444:                         code="CLARIFICATION_REQUIRED",
445:                         message="功率预测配置仍需确认",
446:                         severity="warning",
447:                     ),
448:                     nlu=nlu,
449:                     answer_summary=self._power_resolution_clarification_summary(
450:                         resolution_payload,
451:                         question=question,
452:                     ),
453:                     raw_result={"bom_config_resolution": resolution_payload},
454:                     warnings=["M4 配置解析未完全 resolved，已停止调用 M3 计算，避免编造功率预测。"],
455:                 )
456:             )
457:         if resolution.status in {NOT_FOUND_STATUS, NO_ACTIVE_MODEL_STATUS} or resolution.model_code is None:
458:             return self._empty_response(
459:                 question=question,
460:                 nlu=nlu,
461:                 reason=resolution.message,
462:                 raw={"bom_config_resolution": resolution_payload},
463:             )
464:         if resolution.status != RESOLVED_STATUS:
465:             return self._empty_response(
466:                 question=question,
467:                 nlu=nlu,
468:                 reason=f"BOM 配置映射状态不可用于功率预测：{resolution.status}",
469:                 raw={"bom_config_resolution": resolution_payload},
470:             )
471: 
472:         configuration = resolution.to_prediction_configuration()
473:         supplier_name = nlu.slots.get("supplier_name")
474:         if supplier_name:
475:             configuration["supplier"] = supplier_name
476:         try:
477:             if nlu.intent == "plan_power_supplier_recommendation":
478:                 recommendation = self.power_recommendation_service.recommend(
479:                     model_code=resolution.model_code,
480:                     configuration=configuration,
481:                     target_power_ratio=nlu.slots.get("target_power_ratio"),
482:                     supplier_names=[supplier_name] if supplier_name else None,
483:                 )
484:                 return self._power_recommendation_response(
485:                     question=question,
486:                     nlu=nlu,
487:                     resolution_payload=resolution_payload,
488:                     recommendation=recommendation,
489:                 )
490:             prediction = self.power_prediction_engine.predict(
491:                 model_code=resolution.model_code,
492:                 configuration=configuration,
493:                 supplier_name=supplier_name,
494:             )
495:             return self._power_prediction_response(
496:                 question=question,
497:                 nlu=nlu,
498:                 resolution_payload=resolution_payload,
499:                 prediction=prediction,
500:             )
```

```python
355:                 answer_summary=f"已完成 {len(headers)} 个当前 BOM 版本的物料存在性检查，返回 {len(rows)} 条匹配记录。",
356:                 result_table=PlanBomTableSpec(
357:                     columns=["order_no", "order_name", "version_no", "material_category", "status", "source_file"],
358:                     rows=rows,
359:                 ),
360:                 raw_result={"checked_orders": len(headers), "matched_rows": len(rows)},
361:             )
362:         )
363: 
364:     @staticmethod
365:     def _infer_single_model_code_from_power_candidates(candidates: list[Any]) -> str | None:
366:         """从未确认订单候选中提取唯一版型编码。
367: 
368:         参数：
369:             candidates: M4 返回的候选订单列表，元素可以是 dataclass、Pydantic 或字典。
370:         返回：
371:             当所有可识别候选只指向同一个 `NTxx-xxGDF` 版型时返回该版型；否则返回 None。
372:         业务逻辑：显式配置 no-BOM 评估只可借用“唯一一致的版型线索”，不能在多版型候选中替业务员硬选订单。
373:         """
374: 
375:         model_codes: set[str] = set()
376:         for candidate in candidates or []:
377:             if isinstance(candidate, dict):
378:                 raw_values = [candidate.get("order_name"), candidate.get("raw_file_name")]
379:             else:
380:                 raw_values = [getattr(candidate, "order_name", None), getattr(candidate, "raw_file_name", None)]
381:             for raw_value in raw_values:
382:                 text = str(raw_value or "")
383:                 match = re.search(r"NT[0-9A-Z]+[-/][0-9A-Z]+GDF", text, flags=re.IGNORECASE)
384:                 if match:
385:                     model_codes.add(match.group(0).upper().replace("/", "-"))
386:         return next(iter(model_codes)) if len(model_codes) == 1 else None
387: 
388:     def _power_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
389:         """处理计划 BOM 功率预测 / 供应商推荐问答。
390: 
391:         参数：
392:             question: 原始问题；
393:             nlu: 已完成规则和可选 LLM guardrail 的 NLU 候选。
394: 
395:         返回：
396:             QA 响应。所有配置解析来自 M4，所有数值计算来自 M3，LLM 不参与计算。
397:         """
398: 
399:         tail = (nlu.slots.get("order_tail_no") or [None])[0]
400:         bom_version = (nlu.slots.get("bom_version") or [None])[0]
401:         order_name_hint = nlu.slots.get("order_name_hint")
402:         benchmark = nlu.slots.get("benchmark")
403:         explicit_configuration = dict(nlu.slots.get("explicit_power_configuration") or {})
404:         if benchmark and "benchmark" not in explicit_configuration:
405:             explicit_configuration["benchmark"] = benchmark
406:         if nlu.slots.get("supplier_name") and "supplier" not in explicit_configuration:
407:             explicit_configuration["supplier"] = nlu.slots.get("supplier_name")
408:         if tail:
409:             resolution = self.power_config_resolver.resolve(
410:                 order_no=tail,
411:                 order_name=order_name_hint,
412:                 version_no=bom_version,
413:                 benchmark=benchmark,
414:                 explicit_configuration=explicit_configuration,
415:             )
416:             fallback_model_code = nlu.slots.get("model") or self._infer_single_model_code_from_power_candidates(
417:                 getattr(resolution, "candidates", [])
418:             )
419:             if resolution.status == CANDIDATE_REQUIRED_STATUS and explicit_configuration and fallback_model_code:
420:                 # 业务员有时会把不可靠短尾号和完整计划搭配一起写入问题。
421:                 # 若订单候选未确认，但显式配置 + 版型已经足够让 M4/M3 做 no-BOM 评估，
422:                 # 则转为“显式输入配置”路径，避免把可安全计算的问题降级为候选追问。
423:                 explicit_resolution = self.power_config_resolver.resolve_explicit_configuration(
424:                     model_code=fallback_model_code,
425:                     configuration=explicit_configuration,
426:                 )
427:                 if explicit_resolution.status != CANDIDATE_REQUIRED_STATUS:
428:                     explicit_resolution.warnings.append("已忽略未确认订单候选，按显式输入配置执行 no-BOM 功率推荐。")
429:                     resolution = explicit_resolution
430:         else:
431:             resolution = self.power_config_resolver.resolve_explicit_configuration(
432:                 model_code=nlu.slots.get("model"),
433:                 configuration=explicit_configuration,
434:             )
435:         resolution_payload = resolution.to_dict()
436:         if resolution.status in {CANDIDATE_REQUIRED_STATUS, PARTIAL_STATUS}:
437:             slot_name = "candidate" if resolution.status == CANDIDATE_REQUIRED_STATUS else "power_configuration"
438:             nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), slot_name]))
439:             return self._with_presentation(
440:                 PlanBomQaResponse(
441:                     question=question,
442:                     classification="B",
443:                     status=PlanBomQaStatus(
444:                         code="CLARIFICATION_REQUIRED",
445:                         message="功率预测配置仍需确认",
```

## Focused test coverage snippets

```python
56: class _FakeLogisticsRepository:
57:     """物流问答服务级测试使用的结构化数据替身。
58: 
59:     业务口径：这里不冒充真实数据库验收，只用于验证 planner 和 service 是否把年份、月份、
60:     区域、省份、城市、承运商等槽位正确下推到确定性查询入口。
61:     """
62: 
63:     def hist_customer_mw(
64:         self,
65:         *,
66:         customer_name: str,
67:         year: int | None = None,
68:         months: list[int] | None = None,
69:     ) -> dict[str, Any]:
70:         """模拟历史客户发运量，只有正确客户与月份过滤才返回业务反馈基线。"""
71: 
72:         month_text = "、".join(f"{month}月" for month in (months or []))
73:         scope = f"{year}年{month_text}" if year else "历史累计"
74:         if customer_name == "华阳" and year == 2024 and months == [1]:
75:             return {
76:                 "shipment_mw": 200.187,
77:                 "matched_customer_names": ["华阳新能源有限公司"],
78:                 "scope_label": scope,
79:             }
80:         return {"shipment_mw": 0.0, "matched_customer_names": [], "scope_label": scope}
81: 
82:     def hist_carrier_kpi_by_year(self, *, year: int, region_name: str | None = None) -> dict[str, Any]:
83:         """模拟年度承运商 KPI，并让区域过滤产生不同结果。"""
84: 
85:         if region_name == "西北":
86:             rows = [
87:                 {"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 909.25, "shipment_share_pct": 65.0, "total_fee": 1000.0},
88:                 {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 320.0, "shipment_share_pct": 22.9, "total_fee": 800.0},
89:             ]
90:             return {"total_shipment_mw": 1398.846, "items": rows}
91:         rows = [
92:             {"carrier_name": "苏州晶茂物流有限公司", "shipment_mw": 3730.136, "shipment_share_pct": 21.47, "total_fee": 58250425.0},
93:             {"carrier_name": "浙江英赋嘉供应链科技股份有限公司", "shipment_mw": 3372.578, "shipment_share_pct": 19.41, "total_fee": 81156591.0},
94:         ]
95:         return {"total_shipment_mw": 17374.913, "items": rows}
96: 
97:     def hist_city_mw_rank(
98:         self,
99:         *,
100:         year: int,
101:         top_n: int,
102:         region_name: str | None = None,
103:         province: str | None = None,
104:     ) -> dict[str, Any]:
105:         """模拟历史城市发运量 TopN。"""
106: 
107:         rows = [
108:             {"city": "合肥", "shipment_mw": 320.0},
109:             {"city": "芜湖", "shipment_mw": 220.0},
110:             {"city": "马鞍山", "shipment_mw": 120.0},
111:             {"city": "滁州", "shipment_mw": 80.0},
112:             {"city": "安庆", "shipment_mw": 60.0},
113:         ][:top_n]
114:         return {
115:             "total_shipment_mw": sum(float(row["shipment_mw"]) for row in rows),
116:             "items": rows,
117:             "scope_label": f"{year}年{region_name or province or ''}",
118:         }
119: 
120:     def hist_mw_summary(
121:         self,
122:         *,
123:         year: int | None = None,
124:         months: list[int] | None = None,
125:         region_name: str | None = None,
126:         origin_place: str | None = None,
127:         transport_mode: str | None = None,
128:         carrier_name: str | None = None,
129:         customer_name: str | None = None,
130:     ) -> dict[str, Any]:
131:         """模拟历史总量兜底分支，用于 RED 阶段证明城市 TopN 不应退化到总量。"""
132: 
133:         return {"shipment_mw": 999.0}
134: 
135:     def hist_unit_fee_per_watt(
136:         self,
137:         *,
138:         year: int,
139:         province: str | None = None,
140:         months: list[int] | None = None,
141:         include_extra_fee: bool = False,
142:         transport_mode: str | None = None,
143:         carrier_name: str | None = None,
144:         monthly_breakdown: bool = False,
145:     ) -> dict[str, Any] | list[dict[str, Any]]:
146:         """模拟历史单瓦价，月度分支返回月份表。"""
147: 
148:         if monthly_breakdown:
149:             return [
150:                 {
151:                     "biz_month": "2024-01",
152:                     "total_fee_amount": 1200.0,
153:                     "extra_fee_amount": 0.0,
154:                     "shipment_mw": 100.0,
155:                     "unit_fee_per_watt": 0.000012,
156:                 },
157:                 {
158:                     "biz_month": "2024-02",
159:                     "total_fee_amount": 900.0,
160:                     "extra_fee_amount": 0.0,
161:                     "shipment_mw": 60.0,
162:                     "unit_fee_per_watt": 0.000015,
163:                 },
164:             ]
165:         return {
166:             "total_fee_amount": 2100.0,
167:             "extra_fee_amount": 0.0,
168:             "shipment_mw": 160.0,
169:             "unit_fee_per_watt": 0.00001313,
170:         }
```

```python
474: def test_r50_logistics_company_each_routes_to_carrier_group(logistics_service: LogisticsDataQaService) -> None:
475:     """R50：“物流公司/承运商 + 分别/各”应进入承运商分组，不应退化为年度总量。"""
476: 
477:     result = _ask_logistics(logistics_service, "25年物流公司发货量分别是多少？")
478: 
479:     assert result.status and result.status.code == "OK"
480:     assert result.query_plan.query_key == "hist_carrier_kpi_by_year"
481:     assert result.query_plan.filters["year"] == 2025
482:     assert result.result_table.columns[:2] == ["carrier_name", "shipment_mw"]
483:     assert len(result.result_table.rows) > 1
484: 
485: 
486: def test_r57_carrier_group_respects_region_filter(logistics_service: LogisticsDataQaService) -> None:
487:     """R57：承运商年度分组在用户指定区域时必须下推区域过滤。"""
488: 
489:     global_result = _ask_logistics(logistics_service, "2025年各家物流承运商的承运量分别是多少？")
490:     regional_result = _ask_logistics(logistics_service, "2025年各家物流承运商在西北区域的承运量分别是多少")
491: 
492:     assert regional_result.status and regional_result.status.code == "OK"
493:     assert regional_result.query_plan.query_key == "hist_carrier_kpi_by_year"
494:     assert regional_result.query_plan.filters["region_name"] == "西北"
495:     assert "西北" in regional_result.answer_summary
496:     assert regional_result.result_table.rows
497:     assert regional_result.result_table.rows != global_result.result_table.rows
498: 
499: 
500: @pytest.mark.parametrize(
501:     ("question", "expected_filter"),
502:     [
503:         ("25年华东区域发货量排名前5的城市是哪些，发货量分别是多少", {"year": 2025, "region_name": "华东"}),
504:         ("请列出2025年安徽各城市发运量TOP5及具体数值", {"year": 2025, "province": "安徽"}),
505:         ("2024年安徽省各城市发运量排名前五？", {"year": 2024, "province": "安徽"}),
506:     ],
507: )
508: def test_r51_r52_r53_city_mw_topn_returns_city_table(
509:     logistics_service: LogisticsDataQaService,
510:     question: str,
511:     expected_filter: dict[str, object],
512: ) -> None:
513:     """R51/R52/R53：历史区域或省份下城市发运量 TopN 应返回城市维度表格。"""
514: 
515:     result = _ask_logistics(logistics_service, question)
516: 
517:     assert result.status and result.status.code == "OK"
518:     assert result.query_plan.query_key == "hist_city_mw_rank"
519:     for key, value in expected_filter.items():
520:         assert result.query_plan.filters[key] == value
521:     assert result.query_plan.limit == 5
522:     assert result.result_table.columns == ["city", "shipment_mw"]
523:     assert 1 <= len(result.result_table.rows) <= 5
524:     assert all(row["city"] for row in result.result_table.rows)
525: 
526: 
527: def test_r22_monthly_unit_fee_per_watt_returns_month_rows(logistics_service: LogisticsDataQaService) -> None:
528:     """R22：用户要求 1-12 月单瓦价时，应返回月度总费用、总发运 MW 和单瓦价表。"""
529: 
530:     result = _ask_logistics(logistics_service, "24年 1-12月 目的地是江苏省的单瓦价是多少")
531: 
532:     assert result.status and result.status.code == "OK"
533:     assert result.query_plan.query_key == "hist_unit_fee_per_watt"
534:     assert result.query_plan.dimensions == ["biz_month"]
535:     assert result.result_table.columns == ["biz_month", "total_fee_amount", "extra_fee_amount", "shipment_mw", "unit_fee_per_watt"]
536:     assert 1 <= len(result.result_table.rows) <= 12
537:     assert all(row["biz_month"] for row in result.result_table.rows)
538:     assert all("unit_fee_per_watt" in row for row in result.result_table.rows)
539: 
540: 
```