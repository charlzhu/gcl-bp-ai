from __future__ import annotations

import re
from typing import Any


class LogisticsSlotExtractor:
    """物流域公共槽位抽取器。

    说明：
        1. 本类只负责从自然语言中抽取稳定、可解释的基础槽位；
        2. 不生成 query_key，不生成 SQL，不做 A/B/C 最终边界裁决；
        3. 当前供 NLU Center 与 data-qa planner 复用，减少时间、区域、省份、车型等规则重复。
    """

    YEAR_ALIAS = {"23": 2023, "24": 2024, "25": 2025, "26": 2026}
    REGION_NAMES = ("华东", "华北", "华南", "华中", "西北", "西南", "东北")
    PROVINCE_ALIAS = {
        "江苏省": "江苏",
        "江苏": "江苏",
        "上海市": "上海",
        "上海": "上海",
        "广东省": "广东",
        "广东": "广东",
        "广西壮族自治区": "广西",
        "广西自治区": "广西",
        "广西": "广西",
        "安徽省": "安徽",
        "安徽": "安徽",
        "山东省": "山东",
        "山东": "山东",
        "浙江省": "浙江",
        "浙江": "浙江",
        "湖南省": "湖南",
        "湖南": "湖南",
        "湖北省": "湖北",
        "湖北": "湖北",
        "云南省": "云南",
        "云南": "云南",
        "贵州省": "贵州",
        "贵州": "贵州",
        "四川省": "四川",
        "四川": "四川",
        "新疆维吾尔自治区": "新疆",
        "新疆自治区": "新疆",
        "新疆": "新疆",
        "宁夏回族自治区": "宁夏",
        "宁夏": "宁夏",
        "内蒙古自治区": "内蒙",
        "内蒙古": "内蒙",
        "内蒙": "内蒙",
        # 样例题覆盖全国省份，显式别名优先于宽松正则，避免“请帮我查询河北省”被抽成“请帮我查询河北”。
        "河北省": "河北",
        "河北": "河北",
        "河南省": "河南",
        "河南": "河南",
        "北京市": "北京",
        "北京": "北京",
        "天津市": "天津",
        "天津": "天津",
        "重庆市": "重庆",
        "重庆": "重庆",
        "福建省": "福建",
        "福建": "福建",
        "江西省": "江西",
        "江西": "江西",
        "海南省": "海南",
        "海南": "海南",
        "山西省": "山西",
        "山西": "山西",
        "陕西省": "陕西",
        "陕西": "陕西",
        "辽宁省": "辽宁",
        "辽宁": "辽宁",
        "吉林省": "吉林",
        "吉林": "吉林",
        "黑龙江省": "黑龙江",
        "黑龙江": "黑龙江",
        "甘肃省": "甘肃",
        "甘肃": "甘肃",
        "青海省": "青海",
        "青海": "青海",
        "西藏自治区": "西藏",
        "西藏": "西藏",
    }
    ORIGIN_ALIAS = {"合肥基地": "合肥", "阜宁基地": "阜宁"}
    SYSTEM_BASE_ALIAS = {
        "合肥基地": "1",
        "阜宁基地": "2",
    }
    TRANSPORT_MODE_ALIAS = {
        "铁路": "铁路",
        "铁运": "铁路",
        "公路": "公路",
        "汽运": "公路",
        "多式联运": "多式联运",
        "水路": "水路",
    }
    VEHICLE_TYPE_ALIAS = {
        "17.5车": "17.5",
        "17米五": "17.5",
        "17米5": "17.5",
        "17.5": "17.5",
        "13米车": "13",
        "13米": "13",
        "13m": "13",
        "9.6车": "9.6",
        "9.6米": "9.6",
        "9米6": "9.6",
        "9.6": "9.6",
    }
    STATUS_NAMES = ("SIGNEDFOR", "PREASSIGN", "ASSIGNED", "PRESIGNFOR", "PREALLOCATE", "ALLOCATED", "ENTER", "LEAVE")
    CHINESE_MONTH_ALIAS = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "十一": 11,
        "十二": 12,
    }

    def compact(self, question: str) -> str:
        """压缩问题文本空白。

        参数：
            question: 用户原始问题。

        返回：
            去除连续空白后的文本。
        """

        return re.sub(r"\s+", "", question.strip())

    def extract_year(self, question: str) -> int | None:
        """抽取单一年份。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            2023–2026 范围内的年份；未识别时返回 None。
        """

        compact = self.compact(question)
        match = re.search(r"(?P<year>\d{2,4})年", compact)
        if match:
            return self._resolve_year_token(match.group("year"))
        direct_match = re.search(r"(?<!\d)(20(?:23|24|25|26))(?!\d)", compact)
        if direct_match:
            return int(direct_match.group(1))
        return None

    def extract_years(self, question: str) -> list[int]:
        """抽取文本里出现的全部年份。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            按出现顺序去重后的年份列表。
        """

        compact = self.compact(question)
        years: list[int] = []
        for match in re.finditer(r"(?P<year>\d{2,4})年", compact):
            year = self._resolve_year_token(match.group("year"))
            if year and year not in years:
                years.append(year)
        for match in re.finditer(r"(?<!\d)(20(?:23|24|25|26))(?!\d)", compact):
            year = int(match.group(1))
            if year not in years:
                years.append(year)
        return years

    def extract_months(self, question: str) -> list[int]:
        """抽取月份和正向月份区间。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            按自然顺序去重的月份列表。
        """

        compact = self.compact(question)
        months: list[int] = []
        month_token = r"(?:1[0-2]|[1-9]|十一|十二|十|[一二两三四五六七八九])"
        for match in re.finditer(
            rf"(?P<start>{month_token})月?\s*(?:-|~|至|到)\s*(?P<end>{month_token})月",
            compact,
        ):
            start_month = self._resolve_month_token(match.group("start"))
            end_month = self._resolve_month_token(match.group("end"))
            if 1 <= start_month <= end_month <= 12:
                for month in range(start_month, end_month + 1):
                    if month not in months:
                        months.append(month)
        for match in re.finditer(r"(?<!\d)(?P<month>1[0-2]|[1-9])月份?", compact):
            month = int(match.group("month"))
            if month not in months:
                months.append(month)
        for match in re.finditer(r"(?P<month>十一|十二|十|[一二两三四五六七八九])月份?", compact):
            month = self._resolve_month_token(match.group("month"))
            if month and month not in months:
                months.append(month)
        return months

    def extract_quarter(self, question: str) -> str | None:
        """抽取季度槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            Q1–Q4；未识别时返回 None。
        """

        compact = self.compact(question)
        match = re.search(r"(Q[1-4]|[一二三四]季度)", compact)
        if not match:
            return None
        mapping = {"一季度": "Q1", "二季度": "Q2", "三季度": "Q3", "四季度": "Q4"}
        return mapping.get(match.group(1), match.group(1))

    def extract_region(self, question: str) -> str | None:
        """抽取区域槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            七大区域名称；未识别时返回 None。
        """

        compact = self.compact(question)
        return self._extract_first_match(compact, self.REGION_NAMES)

    def extract_province(self, question: str) -> str | None:
        """抽取省份槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            省份标准简称；未识别时返回 None。
        """

        compact = self.compact(question)
        for alias, normalized in self.PROVINCE_ALIAS.items():
            if alias in compact:
                return normalized
        match = re.search(r"([\u4e00-\u9fa5]{2,6})省", compact)
        if match:
            return match.group(1)
        return None

    def extract_province_list(self, question: str) -> list[str]:
        """抽取“各省(江苏、广东)”这类显式省份列表。"""

        compact = self.compact(question)
        match = re.search(r"各省[（(]([^）)]+)[）)]", compact)
        if not match:
            return []
        result: list[str] = []
        for candidate in re.split(r"[、,，/]+", match.group(1)):
            normalized = candidate.strip().replace("省", "").replace("市", "")
            if normalized:
                result.append(normalized)
        return result

    def extract_origin_place(self, question: str) -> str | None:
        """抽取始发地槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            当前已验证的始发地名称；未识别时返回 None。
        """

        compact = self.compact(question)
        for alias, normalized in self.ORIGIN_ALIAS.items():
            if alias in compact:
                return normalized
        for candidate in ("合肥", "阜宁"):
            if candidate in compact:
                return candidate
        return None

    def extract_system_base_name(self, question: str) -> str | None:
        """抽取 2026 系统侧基地名称。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            系统侧基地名称；未识别时返回 None。
        """

        compact = self.compact(question)
        for base_name in self.SYSTEM_BASE_ALIAS:
            if base_name in compact:
                return base_name
        return None

    def extract_system_base_code(self, question: str) -> str | None:
        """抽取 2026 系统侧基地编码。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            已锁定的系统基地编码；未识别时返回 None。
        """

        base_name = self.extract_system_base_name(question)
        return self.SYSTEM_BASE_ALIAS.get(base_name or "")

    def extract_destination_city(self, question: str) -> str | None:
        """抽取线路问法里的目的城市。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            目的城市简称；未识别或已命中省份时返回 None。
        """

        compact = self.compact(question)
        patterns = (
            r"([\u4e00-\u9fa5]{2,10})城市发运中",
            # “发往苏州的平均运输费用”这类业务问法会把指标写成“运输费用”，
            # 先用非贪婪城市匹配截住目的城市，避免后续 planner 误入澄清分支。
            r"发往([\u4e00-\u9fa5]{2,10}?)(?:的)?(?:平均|总|累计|全年)?(?:每车|单车)?(?:运输费用|运输成本|费用|运费|运价|报价)",
            r"(?:合肥|阜宁)发([\u4e00-\u9fa5]{2,10}?)(?:的)?(?:平均|总|累计|全年)?(?:每车|单车)?(?:运输费用|运输成本|费用|运费|运价|报价)",
            r"发往([\u4e00-\u9fa5]{2,10})(?:13m|13米|17\.5|17米五|17米5|每车|运费|运价|报价)",
            r"(?:合肥|阜宁)发([\u4e00-\u9fa5]{2,10})(?:13m|13米|17\.5|17米五|17米5|运费|运价|报价)",
        )
        for pattern in patterns:
            match = re.search(pattern, compact)
            if not match:
                continue
            city = match.group(1).replace("市", "").replace("省", "").strip()
            # “发往广州的平均运费”这类问法会把“的平均”夹在城市和指标之间，
            # 这里统一去掉指标前缀，避免把“广州的平均”当成城市。
            city = re.sub(r"(的)?(平均|总|累计|全年).*$", "", city).strip()
            if city and city not in self.PROVINCE_ALIAS.values() and city not in self.REGION_NAMES:
                return city
        return None

    def extract_transport_mode(self, question: str) -> str | None:
        """抽取运输方式槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            标准运输方式；未识别时返回 None。
        """

        compact = self.compact(question)
        for alias, normalized in self.TRANSPORT_MODE_ALIAS.items():
            if alias in compact:
                return normalized
        return None

    def extract_vehicle_type(self, question: str) -> str | None:
        """抽取车型槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            标准车型口径；未识别时返回 None。
        """

        compact = self.compact(question)
        for alias, normalized in self.VEHICLE_TYPE_ALIAS.items():
            if alias in compact:
                return normalized
        return None

    def extract_status(self, question: str) -> str | None:
        """抽取系统任务状态槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            系统任务状态枚举；未识别时返回 None。
        """

        upper_compact = self.compact(question).upper()
        return self._extract_first_match(upper_compact, self.STATUS_NAMES)

    def extract_customer_name(self, question: str) -> str | None:
        """抽取客户/项目主体名称。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            轻量清洗后的客户/项目名称；未识别时返回 None。
        """

        compact = self.compact(question)
        patterns = [
            r"客户[:：]?(.+?)(?:总运输费用|运输费用|总运费|运费|总发运量|发运量|总运量|运量|已发出总运量)",
            r"项目名称[:：]?(.+?)(?:已发出总运量|总运量|总发运量|发运量|运量)",
            r"客户(.+?)(?:的总发运量|发运量|总运量|运量|发货的项目地)",
            r"(.+?)项目(?:总发运量|总运量|发运量|运量)",
            r"(.+?)项目(?:24年|25年|2024年|2025年)?(?:发运量|运量)是多少",
        ]
        for pattern in patterns:
            match = re.search(pattern, compact)
            if match:
                return self.clean_subject_phrase(match.group(1))
        return None

    def extract_company_name(self, question: str) -> str | None:
        """抽取 2026 系统侧承运商名称。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            轻量清洗后的承运商名称；未识别时返回 None。
        """

        compact = self.compact(question)
        if "客户" in compact or "项目名称" in compact:
            return None
        patterns = [
            r"(?:\d{2,4}年)?(?:\d{1,2}月份?)?(.+?)(?:总计运费|总运费|运输费用|运费是多少|运费多少|多少钱)",
        ]
        for pattern in patterns:
            match = re.search(pattern, compact)
            if not match:
                continue
            company_name = self.clean_company_phrase(match.group(1))
            if company_name:
                return company_name
        return None

    def extract_time_range(self, question: str, *, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """抽取统一时间槽位。

        参数：
            question: 用户问题或紧凑文本。
            filters: 已有过滤条件，可复用其中的 year / months。

        返回：
            time_range 字典，供 NLU 诊断和后续审计使用。
        """

        compact = self.compact(question)
        filters = filters or {}
        time_range: dict[str, Any] = {}
        year = filters.get("year")
        if year:
            time_range["year"] = year
        years = self.extract_years(compact)
        if years:
            time_range["years"] = years
            time_range.setdefault("year", years[0] if len(years) == 1 else None)
        months = filters.get("months") or self.extract_months(compact)
        if months:
            time_range["months"] = months
        quarter = self.extract_quarter(compact)
        if quarter:
            time_range["quarter"] = quarter
        if any(keyword in compact for keyword in ("年初至今", "截至目前", "当前累计", "当前为止")):
            time_range["year_to_date"] = True
        relative_range = self._extract_first_match(compact, ("近7天", "近30天", "近一个月", "近三个月"))
        if relative_range:
            time_range["relative_range"] = relative_range
        return time_range

    def resolve_source_scope(self, question: str, *, time_range: dict[str, Any] | None = None) -> str:
        """判断数据来源层。

        参数：
            question: 用户问题或紧凑文本。
            time_range: 已抽取时间槽位；为空时内部重新抽取。

        返回：
            historical_2023_2025 / system_2026 / mixed / unknown。
        """

        compact = self.compact(question)
        time_range = time_range or self.extract_time_range(compact)
        years = [item for item in time_range.get("years", []) if isinstance(item, int)]
        year = time_range.get("year")
        if isinstance(year, int) and year not in years:
            years.append(year)
        if not years:
            if "历史" in compact or "历史台账" in compact:
                return "historical_2023_2025"
            if "2026" in compact or "系统" in compact:
                return "system_2026"
            return "unknown"
        has_history = any(year in {2023, 2024, 2025} for year in years)
        has_system = any(year >= 2026 for year in years)
        if has_history and has_system:
            return "mixed"
        if has_system:
            return "system_2026"
        return "historical_2023_2025"

    def extract_core_filters(self, question: str) -> dict[str, Any]:
        """抽取可复用的核心过滤槽位。

        参数：
            question: 用户问题或紧凑文本。

        返回：
            过滤条件字典；仅包含已明确识别的槽位。
        """

        filters: dict[str, Any] = {}
        region = self.extract_region(question)
        if region:
            filters["region"] = region
            filters["region_name"] = region
        province = self.extract_province(question)
        if province:
            filters["province"] = province
        status = self.extract_status(question)
        if status:
            filters["status"] = status
        origin_place = self.extract_origin_place(question)
        if origin_place:
            filters["origin_place"] = origin_place
        transport_mode = self.extract_transport_mode(question)
        if transport_mode:
            filters["transport_type"] = transport_mode
            filters["transport_mode"] = transport_mode
        vehicle_type = self.extract_vehicle_type(question)
        if vehicle_type:
            filters["vehicle_type"] = vehicle_type
        base_name = self.extract_system_base_name(question)
        if base_name:
            filters["base_name"] = base_name
        base_code = self.extract_system_base_code(question)
        if base_code:
            filters["base_code"] = base_code
        return filters

    def clean_subject_phrase(self, raw_text: str) -> str:
        """清洗客户/项目主体短语。

        参数：
            raw_text: 待清洗的主体片段。

        返回：
            去掉题号、时间、固定业务前后缀后的主体名称。
        """

        cleaned = raw_text
        cleaned = re.sub(r"^问题\d+[:：]?", "", cleaned)
        cleaned = re.sub(r"^\d+\.", "", cleaned)
        cleaned = cleaned.replace("项目名称", "")
        cleaned = re.sub(r"\d{2,4}年", "", cleaned)
        cleaned = re.sub(r"\d{1,2}月份?", "", cleaned)
        cleaned = cleaned.replace("全年", "")
        cleaned = cleaned.replace("已发出", "")
        cleaned = cleaned.replace("总计", "")
        cleaned = cleaned.replace("发货的", "")
        cleaned = cleaned.replace("发货", "")
        cleaned = cleaned.replace("项目", "")
        # “客户创维客户总运费”中第二个“客户”是口语化后缀，不是客户主体名称。
        cleaned = re.sub(r"客户$", "", cleaned)
        return cleaned.strip(" ：:，,。？！?")

    def clean_company_phrase(self, raw_text: str) -> str:
        """清洗承运商主体短语。

        参数：
            raw_text: 待清洗的承运商片段。

        返回：
            去掉题号、时间、基地和查询动词后的承运商名称。
        """

        cleaned = raw_text
        cleaned = re.sub(r"^问题\d+[:：]?", "", cleaned)
        cleaned = re.sub(r"^\d+\.", "", cleaned)
        cleaned = re.sub(r"\d{2,4}年", "", cleaned)
        # 月份范围不是承运商主体，例如“2026年1到3月每个月的总运费”。
        # 这里先清掉区间月份，避免后续宽松正则把“1到3月每个月的”误当物流公司。
        cleaned = re.sub(r"\d{1,2}\s*(?:到|至|-|—|~)\s*\d{1,2}\s*月", "", cleaned)
        cleaned = re.sub(r"\d{1,2}月份?", "", cleaned)
        cleaned = cleaned.replace("承运商", "")
        cleaned = cleaned.replace("物流公司", "")
        cleaned = cleaned.replace("物流供应商", "")
        cleaned = cleaned.replace("全年", "")
        # 按月展示词只表达分组颗粒度，不是公司名称。
        cleaned = re.sub(r"(?:每个月|每月|各月|按月|月度|这几个月|这三个月)的?", "", cleaned)
        # “晶茂物流运费占全年总运费的比例”这类占比问法里，正则会把
        # “运费占全年”带进主体片段；这里裁掉统计口径后缀，只保留承运商名称。
        cleaned = re.sub(r"(?:运费|运输费用)?占.*$", "", cleaned)
        cleaned = cleaned.replace("总计", "")
        cleaned = cleaned.replace("累计", "")
        cleaned = cleaned.replace("各按", "")
        cleaned = cleaned.replace("查询", "")
        cleaned = cleaned.replace("帮我做一个", "")
        cleaned = cleaned.replace("帮我查一下", "")
        cleaned = cleaned.replace("帮我看一下", "")
        cleaned = cleaned.replace("查一下", "")
        cleaned = cleaned.replace("看一下", "")
        # “全年总运输费用”会被宽松正则截成“晶茂物流总”，尾部“总”只是指标前缀。
        cleaned = re.sub(r"总$", "", cleaned)
        for base_name in self.SYSTEM_BASE_ALIAS:
            cleaned = cleaned.replace(base_name, "")
        return cleaned.strip(" ：:，,。？！?")

    def _resolve_year_token(self, raw: str) -> int | None:
        """解析年份 token。

        参数：
            raw: 两位、三位或四位年份文本。

        返回：
            标准四位年份；无法解析时返回 None。
        """

        if len(raw) == 2:
            return self.YEAR_ALIAS.get(raw)
        if len(raw) == 3 and raw.startswith("0"):
            return self.YEAR_ALIAS.get(raw[-2:])
        try:
            return int(raw)
        except ValueError:
            return None

    def _resolve_month_token(self, raw: str) -> int:
        """解析月份 token。

        参数：
            raw: 阿拉伯数字或中文月份文本。

        返回：
            1–12 的月份；无法解析时返回 0。
        """

        if raw.isdigit():
            return int(raw)
        return self.CHINESE_MONTH_ALIAS.get(raw, 0)

    @staticmethod
    def _extract_first_match(text: str, candidates: tuple[str, ...]) -> str | None:
        """从候选词里提取第一个命中项。

        参数：
            text: 待匹配文本。
            candidates: 候选词列表。

        返回：
            第一个命中的候选词；未命中时返回 None。
        """

        for item in candidates:
            if item in text:
                return item
        return None
