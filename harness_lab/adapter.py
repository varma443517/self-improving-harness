"""DataAdapter: plugs small data-engineering tasks into Harness².

Harness² owns the loop (propose -> probe -> compose -> select -> reflect). It knows nothing
about CSVs or joins. Everything it needs to know about OUR work comes through this class, in
five jobs:

  1. What is the work?          tasks, domain_of, task_prompt, task_files
  2. Where does the agent start? base_harness, validate_tree
  3. Run it                      execute
  4. What happened?              delivered, trajectory, deliverable_text, deliverable_files
  5. Was it right?               score   <- behind the wall: never called during the loop

The "worker" here is deterministic: a task names one pipeline script, and execute() runs the
harness's copy of that script. When an editor changes the script, the next run uses the new
version. A real LLM agent would replace that one subprocess call.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from harness2.core import tree
from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
from harness2.substrate.opencode import OpencodeSubstrate

REPO = Path(__file__).resolve().parents[1]
TASKS = REPO / "tasks"
ANSWERS = REPO / "answers"  # read by score() and nothing else
BASE = REPO / "base_harness"

DOMAIN = "data-engineering"
MAIN_TASKS = ["orders-join", "dedupe-events", "schema-drift", "null-revenue", "timezone-daily"]


class DataAdapter:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.substrate = OpencodeSubstrate()
        channel = ChannelSpec("opencode", "local/scripted")
        self.spec = BenchSpec(
            name="data",
            runs_root=self.root / "runs",
            install_mode="workspace_config",
            # This text reaches the editors. Harness² refuses words such as "score" or
            # "grader" here, so editors improve the work, not the measurement.
            prompts=BenchPrompts(
                work="clean, join and summarise small CSV datasets for an analytics team",
                deliverable_word="output table",
            ),
            channels={"proposer": channel, "selector": channel},
            # Belt and braces: Harness² refuses to copy matching paths into any editor folder.
            leak_globs=("answers/*", "*.answer.csv"),
        )
        # Copy the starting harness out of the repo, so no run can ever edit the original.
        tree.write_tree(
            self.substrate.surface(),
            tree.read_tree(self.substrate.surface(), BASE),
            self.base_harness(),
            stubs=False,
        )

    # ---- 1. What is the work? -------------------------------------------------------------
    def tasks(self, split: str = "all") -> list[str]:
        return list(MAIN_TASKS)  # fixed order: the library grows task by task

    def domain_of(self, task_id: str) -> str:
        return DOMAIN  # one domain, so every task shares one library

    def task_prompt(self, task_id: str) -> str:
        return (TASKS / task_id / "prompt.md").read_text(encoding="utf-8")

    def task_files(self, task_id: str) -> Path:
        return TASKS / task_id / "input"

    def _meta(self, task_id: str) -> dict:
        return task_meta(task_id)

    # ---- 2. Where does the agent start? ---------------------------------------------------
    def base_harness(self) -> Path:
        return self.root / "base"

    def validate_tree(self, harness: tree.Tree) -> None:
        # The message is fed back to the editor word for word, so say how to fix it.
        missing = [
            f"scripts/{name}"
            for name in sorted(p.name for p in (BASE / "scripts").glob("*.py"))
            if f"scripts/{name}" not in harness
        ]
        if missing:
            raise ValueError(
                "every pipeline script must stay in the harness; restore: " + ", ".join(missing)
            )

    # ---- 3. Run it ---------------------------------------------------------------------
    def execute(
        self, task_id: str, harness_dir: Path | None, run_id: str, *, timeout: int | None = None
    ) -> Path:
        run_dir = self.root / "executions" / run_id
        if (run_dir / "trajectory.md").is_file():
            return run_dir  # idempotent by run_id: a resumed sweep reuses finished runs
        run_dir.mkdir(parents=True, exist_ok=True)

        script = self._meta(task_id)["script"]
        harness = Path(harness_dir) if harness_dir else self.base_harness()
        result = subprocess.run(
            [
                sys.executable,
                str(harness / script),
                str(self.task_files(task_id)),
                str(run_dir / "output.csv"),
            ],
            capture_output=True,
            text=True,
            timeout=timeout or 60,
        )
        # Harness²'s shared transcript grammar. A crash is evidence too, so it is recorded,
        # never raised.
        lines = [
            f"[ACTION] python {script} input/ output.csv",
            "[OBSERVATION]",
            result.stdout.strip() or "(no output)",
        ]
        if result.returncode:
            lines += ["[ERROR]", "\n".join(result.stderr.strip().splitlines()[-3:])]
        (run_dir / "trajectory.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return run_dir

    # ---- 4. What happened? ----------------------------------------------------------------
    def delivered(self, run_dir: Path) -> bool:
        return (Path(run_dir) / "output.csv").is_file()

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        return (Path(run_dir) / "trajectory.md").read_text(encoding="utf-8")[:obs_trunc]

    def deliverable_text(self, run_dir: Path) -> str:
        out = Path(run_dir) / "output.csv"
        return out.read_text(encoding="utf-8") if out.is_file() else ""

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        text = self.deliverable_text(run_dir)
        return {"output.csv": text} if text else {}

    # ---- 5. Was it right? (behind the wall) --------------------------------------------
    def score(self, run_dir: Path, task_id: str) -> dict | None:
        """Compare output.csv with the answer file. Called by our bench AFTER the loop only."""
        expected = _rows(ANSWERS / f"{task_id}.csv")
        got = Path(run_dir) / "output.csv"
        if not got.is_file():
            return {"correct": False, "reason": "no output.csv"}
        rows = _rows(got)
        return {"correct": rows == expected, "rows": len(rows), "expected_rows": len(expected)}


def task_meta(task_id: str) -> dict:
    """The task's meta.json: its id and the pipeline script that does the work."""
    return json.loads((TASKS / task_id / "input" / "meta.json").read_text(encoding="utf-8"))


def _rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [[cell.strip() for cell in row] for row in csv.reader(f) if row]
