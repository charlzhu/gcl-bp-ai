from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "2025年物流发运总台账.xlsx"
OUT = Path(__file__).with_name("source_oracle_probe.out")

df = pd.read_excel(SOURCE, sheet_name="Sheet1")


def text_series(column: str) -> pd.Series:
    return df[column].fillna("").astype(str).str.strip()


def numeric(column: str, frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce")

origin = text_series("始发地")
city = text_series("城市")
province = text_series("省份")
address = text_series("地址")
vehicle = text_series("要求中标车辆型号")
base = np.logical_and(origin.str.contains("合肥", na=False), vehicle.str.contains("17.5", na=False))

cases = [
    ("city==广州", np.logical_and(base, city == "广州")),
    ("city contains 广州", np.logical_and(base, city.str.contains("广州", na=False))),
    ("address contains 广州", np.logical_and(base, address.str.contains("广州", na=False))),
    ("province广东", np.logical_and(base, province == "广东")),
    (
        "province广东 city contains 广州",
        np.logical_and.reduce([base, province == "广东", city.str.contains("广州", na=False)]),
    ),
    (
        "province广东 address contains 广州",
        np.logical_and.reduce([base, province == "广东", address.str.contains("广州", na=False)]),
    ),
]

lines: list[str] = []
lines.append(f"source={SOURCE.name} shape={df.shape}")
lines.append(f"合肥+17.5 rows={int(base.sum())}")
for label, mask in cases:
    d = df[mask].copy()
    lines.append(f"\n--- {label} rows={len(d)}")
    if d.empty:
        continue
    for col in ["单价/车", "总费用(元)", "车次", "元/瓦"]:
        vals = numeric(col, d)
        lines.append(
            f"{col}: count={int(vals.notna().sum())} min={vals.min()} max={vals.max()} avg={vals.mean()} sum={vals.sum()}"
        )
    cols = [
        "发货日期",
        "始发地",
        "省份",
        "城市",
        "地址",
        "要求中标车辆型号",
        "车次",
        "物流公司",
        "单价/车",
        "总费用(元)",
        "元/瓦",
        "询比价编号",
    ]
    lines.append(d[cols].head(30).to_string(index=False))

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
