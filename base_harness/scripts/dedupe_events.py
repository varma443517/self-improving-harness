"""Clean an event log so each real event appears once.

Usage: python scripts/dedupe_events.py INPUT_DIR OUTPUT_CSV
"""

import sys
from pathlib import Path

import pandas as pd

src, out = Path(sys.argv[1]), Path(sys.argv[2])

events = pd.read_csv(src / "events.csv", dtype=str)
before = len(events)
events = events.drop_duplicates(subset=["event_id"])
events.to_csv(out, index=False)

payments = int((events["action"] == "pay").sum())
print(f"{before} events in, {len(events)} kept, {payments} payments")
