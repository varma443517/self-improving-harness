"""What happens when a harness editor breaks the harness?

Harness² lets an LLM *editor* rewrite the files around a frozen agent. Editors make mistakes,
so every proposed harness is validated before it is ever run. This experiment sabotages two
editors on purpose and records what the framework does:

    inv1  deletes scripts/summarize.py on BOTH attempts  -> rejected, retried, falls back to base
    dom1  deletes it on its FIRST attempt only           -> rejected, retried, accepted

It reuses Harness²'s offline demo task (sum a ledger of signed amounts), so it runs in seconds
with no model and no API keys. Run it with `make experiment`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from harness2.core.schedule import run_domain
from harness2.demo import BASE_SCRIPT, DemoAdapter, DemoProposer

SCRIPT = "scripts/summarize.py"  # the one file the demo agent cannot work without


class SabotageProposer(DemoProposer):
    """The demo's scripted editor, plus a deliberate mistake on chosen attempts.

    Every editor call has a label such as "inv1.a1" -- stage `inv1`, attempt 1. A retry is
    "inv1.a2". Selection ("select.*") and reflection ("experience.*") calls are left alone.
    """

    def __init__(self, *args, sabotage: set[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.sabotage = sabotage  # labels whose edit will delete the script
        self.rejections: dict[str, str] = {}  # label -> the error Harness² sent back

    def call(self, mission, context_dir, label, **kwargs):
        is_edit = not label.startswith(("select.", "experience."))
        harness = Path(context_dir) / "harness"

        # On a retry, Harness² hands the editor its OWN rejected files to repair (it does not
        # start over). The demo editor expects the script to exist, so a "repair" puts it back.
        if is_edit and not (harness / SCRIPT).exists():
            (harness / SCRIPT).write_text(BASE_SCRIPT, encoding="utf-8")

        # The retry prompt quotes why the previous attempt was rejected -- capture it.
        if "PREVIOUS ATTEMPT WAS REJECTED" in mission:
            reason = mission.split("REJECTED", 1)[1].strip().splitlines()[0]
            self.rejections[label] = reason

        reply = super().call(mission, context_dir, label, **kwargs)  # the normal, good edit

        if label in self.sabotage and reply.workspace is not None:
            (Path(reply.workspace) / SCRIPT).unlink(missing_ok=True)  # ...then break it
        return reply


@dataclass
class StageResult:
    label: str
    attempts: int
    fell_back: bool
    answer: str
    error: str


def run(out: Path) -> tuple[list[StageResult], dict[str, str]]:
    """Run one ledger task at k=1 in parallel mode; return each stage and the rejections."""
    out = out.resolve()
    adapter = DemoAdapter(out)
    prop = SabotageProposer(
        adapter.spec.channels["proposer"],
        sabotage={"inv1.a1", "inv1.a2", "dom1.a1"},
    )
    run_domain(
        "accounting",
        ["ledger-1"],
        1,  # k=1: one INV candidate, one DOM candidate, one composition
        adapter=adapter,
        prop=prop,
        runs_root=adapter.spec.runs_root,
        library_root=out / "library",
        modes=("agg",),  # "agg" is the on-disk name for parallel recursion
    )

    # Harness² records every stage of the task in summary.json.
    summary = json.loads((out / "runs/demo-oc-agg1/ledger-1/summary.json").read_text())
    executions = out / "executions/demo-oc-agg1/ledger-1"

    def answer(label: str) -> str:
        return (executions / label / "answer.txt").read_text().strip()

    stages = [StageResult("base1", 0, False, answer("base1"), "")]
    for s in summary["modes"]["agg"]["stages"]:
        stages.append(
            StageResult(s["label"], s["attempts"], s["fell_back"], answer(s["label"]), s["error"])
        )
    return stages, prop.rejections


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "out/broken-edit")
    stages, rejections = run(out)

    print("\nRejections sent back to the editor:")
    for label, reason in sorted(rejections.items()):
        print(f"  {label}: {reason}")

    print(f"\n{'stage':6} {'attempts':>8}  {'fell back':9}  answer")
    for s in stages:
        print(f"{s.label:6} {s.attempts:>8}  {str(s.fell_back):9}  {s.answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
