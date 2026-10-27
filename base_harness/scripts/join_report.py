"""Customer totals report: one row per customer with their order total.

Usage: python scripts/join_report.py INPUT_DIR OUTPUT_CSV
"""

import csv
import sqlite3
import sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])

db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE customers (id TEXT, name TEXT)")
db.execute("CREATE TABLE orders (order_id TEXT, customer_id TEXT, amount REAL)")
with open(src / "customers.csv") as f:
    db.executemany("INSERT INTO customers VALUES (:id, :name)", csv.DictReader(f))
with open(src / "orders.csv") as f:
    db.executemany(
        "INSERT INTO orders VALUES (:order_id, :customer_id, :amount)", csv.DictReader(f)
    )

rows = db.execute(
    """
    SELECT c.id, c.name, COALESCE(SUM(o.amount), 0) AS total
    FROM customers c
    JOIN orders o ON o.customer_id = c.id
    GROUP BY c.id, c.name
    ORDER BY c.id
    """
).fetchall()

with open(out, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["customer_id", "name", "total"])
    for customer_id, name, total in rows:
        writer.writerow([customer_id, name, f"{total:.2f}"])

customers = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
print(f"{customers} customers in, {len(rows)} rows written to output.csv")
