"""Revenue summary: average revenue per sale and how many sales have none recorded.

Usage: python scripts/revenue_stats.py INPUT_DIR OUTPUT_CSV
"""

import sys
from pathlib import Path

import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])

sales = pd.read_csv(src / "sales.csv")
revenue = sales["revenue"].fillna(0)
average = revenue.mean()
missing = int(revenue.isna().sum())

pd.DataFrame(
    {"metric": ["average_revenue", "missing_values"], "value": [f"{average:.2f}", missing]}
).to_csv(out, index=False)
print(f"{len(sales)} sales, average {average:.2f}, {missing} missing")
