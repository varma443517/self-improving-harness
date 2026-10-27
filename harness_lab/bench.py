"""Run the five data tasks through Harness² and score base vs refined, after the loop.

    uv run python -m harness_lab.bench [OUT_DIR] [--k K]

The loop never sees the answers. Only once run_domain() has finished do we call the adapter's
score() on two runs per task: the base harness, and the final Harness² selected.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from harness2.core.schedule import run_domain

from .adapter import DOMAIN, MAIN_TASKS, DataAdapter
from .coach import ScriptedCoach


@dataclass
class Row:
    task: str
    base_correct: bool
    final_correct: bool
    rollouts: int  # how many times the worker ran
    sessions: int  # how many editor/composer sessions ran
    lesson: str  # the cue saved to the library, or ""
    library_before: int  # lessons already in the library when this task started


def run(
    out: Path,
    tasks=MAIN_TASKS,
    *,
    k: int = 1,
    coach: ScriptedCoach | None = None,
    mode: str = "agg",
) -> list[Row]:
    out = Path(out).resolve()
    adapter = DataAdapter(out)
    coach = coach or ScriptedCoach(adapter.spec.channels["proposer"])
    result = run_domain(
        DOMAIN,
        list(tasks),
        k,
        adapter=adapter,
        prop=coach,
        runs_root=adapter.spec.runs_root,
        library_root=out / "library",
        modes=(mode,),
    )

    rows = []
    for task, info in zip(tasks, result["tasks"], strict=True):
        summary = json.loads(
            next(adapter.spec.runs_root.glob(f"*/{task}/summary.json")).read_text()
        )
        selection = summary["selections"][mode]
        ledger = summary["modes"][mode]["ledger"]
        # The wall comes down only here, after selection is final.
        base = adapter.score(Path(summary["base"][0]["run_dir"]), task)
        final = adapter.score(Path(selection["chosen_run_dir"]), task)
        rows.append(
            Row(
                task=task,
                base_correct=base["correct"],
                final_correct=final["correct"],
                rollouts=ledger["R"],
                sessions=ledger["P"],
                lesson=(selection.get("experience") or {}).get("cue", ""),
                library_before=info["library_entries_before"][mode],
            )
        )
    return rows


def table(rows: list[Row]) -> str:
    mark = {True: "✓ right", False: "✗ wrong"}
    lines = [
        "| task | base harness | after Harness² | worker runs | editor sessions | lesson saved |",
        "|---|---|---|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r.task}` | {mark[r.base_correct]} | {mark[r.final_correct]} | "
            f"{r.rollouts} | {r.sessions} | {r.lesson or '—'} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", nargs="?", default="out/bench", type=Path)
    parser.add_argument("--k", type=int, default=1)
    args = parser.parse_args()
    rows = run(args.out, k=args.k)
    print(table(rows))
    fixed = sum(r.final_correct and not r.base_correct for r in rows)
    print(
        f"\n{fixed} of {len(rows)} tasks went from wrong to right; answers were read only after "
        "selection."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
