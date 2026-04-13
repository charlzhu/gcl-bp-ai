from datetime import datetime


def parse_month(value: str):
    return datetime.strptime(value, "%Y-%m")


def format_month(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def month_index(value: str) -> int:
    parsed = parse_month(value)
    return parsed.year * 12 + parsed.month


def shift_month(value: str, delta: int) -> str:
    parsed = parse_month(value)
    total = parsed.year * 12 + (parsed.month - 1) + delta
    year, month_zero = divmod(total, 12)
    return format_month(year, month_zero + 1)


def months_between(start_month: str, end_month: str) -> int:
    return month_index(end_month) - month_index(start_month) + 1


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
