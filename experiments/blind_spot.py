"""Where the method breaks, on purpose: a blind spot every editor shares.

Three join tasks run in order through one shared library. The coach knows every fix EXCEPT
the join fix, so on its own it never thinks of LEFT JOIN.

    orders-join-a  nobody tries LEFT JOIN -> every run agrees -> no contrast, no lesson
    orders-join-b  one DOM editor is "curious" and tries it -> 4 rows vs 3 -> lesson saved
    orders-join-c  still blind, but reads the library cue from task b -> fixed

This is the paper's failure mode ("a wrong premise shared by every candidate") and its
remedy (the outer loop's library) on a task small enough to read in full.

    uv run python experiments/blind_spot.py [OUT_DIR]
"""

from __future__ import annotations

import sys
from pathlib import Path

from harness_lab import bench
from harness_lab.adapter import DataAdapter
from harness_lab.coach import ScriptedCoach
from harness_lab.fixes import BY_ID

TASKS = ["orders-join-a", "orders-join-b", "orders-join-c"]


def run(out: Path):
    channel = DataAdapter(Path(out).resolve()).spec.channels["proposer"]
    coach = ScriptedCoach(
        channel,
        knows=frozenset(BY_ID) - {"join"},  # the shared blind spot
        curious={"orders-join-b": frozenset({"join"})},  # one editor tries something new
    )
    rows = bench.run(out, TASKS, coach=coach)
    return rows, coach.log


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out/blind-spot")
    rows, log = run(out)
    print(bench.table(rows))
    print("\nWhy each join fix was applied:")
    for entry in log:
        print(f"  {entry['task']:14} {entry['label']:7} {entry['fix']:5} <- {entry['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
