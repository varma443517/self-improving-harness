"""ScriptedCoach: a deterministic stand-in for the coach model.

In the paper, a strong model (Claude Opus 4.8) plays four roles. Harness² calls the same
`Proposer.call()` for all of them and tells them apart by the call's label:

  "inv1.a1", "dom2.a1"   an INV or DOM editor proposes a candidate harness (attempt a1, a2)
  "agg1.a1", "c1.a1"     a composer merges candidates (parallel "agg", sequential "c")
  "select.agg2"          the blind selector picks one final (only when k > 1)
  "experience.agg1"      the reflector writes a lesson for the library

Each call gets a folder of evidence (`context_dir`), never the answers. This coach reads that
evidence exactly as a model would, but its "judgement" is a fixed table of known fixes
(fixes.py). Three switches let experiments shape what it knows:

  knows    fix ids it applies whenever the task's script needs them
  curious  {task_id: fix ids} it tries on that task only, even if it does not know them
  library  it always reads context/library/INDEX.md, and applies a fix whose cue it finds
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

from harness2.core.proposer import Proposer, Reply

from .fixes import BY_ID, FIXES

LANES = {"inv": "INV", "dom": "DOM"}


@dataclass
class ScriptedCoach(Proposer):
    knows: frozenset[str] = frozenset(BY_ID)
    curious: dict[str, frozenset[str]] = field(default_factory=dict)
    # Every fix the editors applied, and why: "known", "curious" or "library".
    log: list[dict] = field(default_factory=list)

    def call(self, mission, context_dir, label, **kwargs) -> Reply:
        ctx = Path(context_dir)
        workspace = None
        if label.startswith("select."):
            text = self._select(ctx)
        elif label.startswith("experience."):
            text = self._reflect(ctx)
        elif label[:3] in LANES:
            text, workspace = self._propose(ctx, label, LANES[label[:3]])
        else:  # agg* or c*: a composer
            text, workspace = self._compose(ctx)
        reply = Reply(label=label, text=text, ok=True, attempts=1, workspace=workspace)
        self._calls.append(reply)
        return reply

    # ---- editor: propose one candidate ------------------------------------------------
    def _propose(self, ctx: Path, label: str, lane: str) -> tuple[str, Path]:
        harness = ctx / "harness"
        task = _task_meta(ctx)
        index = ctx / "library" / "INDEX.md"
        library = index.read_text() if index.is_file() else ""
        notes = []
        for fix in FIXES:
            if fix.lane != lane or fix.script != task["script"]:
                continue  # stay in this editor's lane, and only touch the script this task ran
            why = (
                "known"
                if fix.id in self.knows
                else "curious"
                if fix.id in self.curious.get(task["id"], ())
                else "library"
                if fix.cue in library
                else None
            )
            if why is None:
                continue  # a blind spot: this editor would not think of the fix
            path = harness / fix.script
            before = path.read_text()
            path.write_text(fix.apply(before))
            if path.read_text() != before:
                notes.append(f"{fix.script}: {fix.change}")
                self.log.append({"task": task["id"], "label": label, "fix": fix.id, "why": why})
        if not notes:
            notes.append("No edit: nothing in this lane looked wrong for this task.")
        return f"<notes>{'; '.join(notes)}</notes>", harness

    # ---- composer: merge what the candidates changed ---------------------------------
    def _compose(self, ctx: Path) -> tuple[str, Path]:
        harness = ctx / "harness"
        # Compare every candidate with the harness as it was BEFORE merging, so a candidate
        # that left a script alone can never undo another candidate's edit.
        start = {p.name: p.read_text() for p in (harness / "scripts").glob("*.py")}
        merged = []
        for cand in sorted((ctx / "pool").glob("*/harness")):
            for script in sorted((cand / "scripts").glob("*.py")):
                if script.read_text() != start.get(script.name):
                    (harness / "scripts" / script.name).write_text(script.read_text())
                    merged.append(f"scripts/{script.name} from {cand.parent.name}")
        notes = "Merged " + ", ".join(merged) if merged else "No candidate changed a script."
        return f"<notes>{notes}</notes>", harness

    # ---- selector: pick one anonymised final ---------------------------------------
    def _select(self, ctx: Path) -> str:
        first = sorted((ctx / "candidates").glob("*.md"))[0].stem
        return (
            "<why>Scripted coach: every final carries the same merged edits; "
            f"take the first.</why>\n```choice\n{first}\n```"
        )

    # ---- reflector: a lesson only when two runs actually differed ------------------
    def _reflect(self, ctx: Path) -> str:
        chosen = json.loads((ctx / "adoption.json").read_text())["chosen_label"]
        base_out = _output(ctx, "base1")
        chosen_out = _output(ctx, chosen)
        changed = [
            fix
            for fix in FIXES
            if (ctx / "harness" / fix.script).is_file()
            and fix.applied_to((ctx / "harness" / fix.script).read_text())
            and not fix.applied_to((ctx / "base_harness" / fix.script).read_text())
        ]
        if not changed or base_out == chosen_out:
            return "NO_ENTRY"  # no edit, or no visible contrast: nothing earned a lesson
        fix = changed[0]
        observed = f"base1 gave {_describe(base_out)}; {chosen} gave {_describe(chosen_out)}"
        return (
            f"<edits>\ncomponent: {fix.script}\ncandidates: {chosen}\n"
            f"change: {fix.change}\nobserved: {observed}\n"
            "verdict: changed the output\n</edits>\n\n"
            f"<experience>\ncue: {fix.cue}\nlesson: {fix.lesson}\n"
            f"evidence: The {fix.script} edit changed the run: {observed}.\n"
            "confidence: high for this observed contrast\n</experience>"
        )


def _task_meta(ctx: Path) -> dict:
    return json.loads((ctx / "source" / "meta.json").read_text())


def _output(ctx: Path, label: str) -> str | None:
    # Harness² stores each run's deliverable for the reflector with a .txt suffix.
    for name in ("output.csv.txt", "output.csv"):
        path = ctx / "deliverables" / label / name
        if path.is_file():
            return path.read_text()
    return None


def _describe(text: str | None) -> str:
    if text is None:
        return "no output.csv"
    rows = list(csv.reader(io.StringIO(text)))[1:]
    return f"{len(rows)} rows ({'; '.join(','.join(r) for r in rows[:5])})"
