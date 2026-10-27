"""Load every daily orders file into one table.

Usage: python scripts/load_daily.py INPUT_DIR OUTPUT_CSV
"""

import csv
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])

rows = []
for path in sorted(src.glob("day_*.csv")):
    with open(path) as f:
        for row in csv.DictReader(f):
            rows.append({"order_id": row["order_id"], "amount": row["amount"]})
    print(f"loaded {path.name}")

with open(out, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["order_id", "amount"])
    writer.writeheader()
    writer.writerows(rows)
print(f"{len(rows)} rows written to output.csv")
