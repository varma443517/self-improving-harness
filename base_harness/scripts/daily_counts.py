"""Sales per business day for one store.

Usage: python scripts/daily_counts.py INPUT_DIR OUTPUT_CSV
"""

import json
import sys
from pathlib import Path

import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])

meta = json.loads((src / "meta.json").read_text())
sales = pd.read_csv(src / "sales.csv")
ts = pd.to_datetime(sales["ts_utc"], utc=True)
sales["day"] = ts.dt.date

counts = sales.groupby("day").size().reset_index(name="sales")
counts.to_csv(out, index=False)
print(f"{len(sales)} sales over {len(counts)} days (store time zone {meta['timezone']})")
