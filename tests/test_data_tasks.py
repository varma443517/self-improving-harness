"""The data tasks, the loop around them, and the wall between the loop and the answers."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from harness_lab import bench
from harness_lab.adapter import ANSWERS, BASE, MAIN_TASKS, TASKS, DataAdapter, _rows, task_meta
from harness_lab.fixes import FIXES

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import blind_spot  # noqa: E402


def _run_script(harness: Path, task: str, out: Path) -> Path:
    script = task_meta(task)["script"]
    subprocess.run(
        [sys.executable, str(harness / script), str(TASKS / task / "input"), str(out)],
        capture_output=True,
        text=True,
    )
    return out


@pytest.mark.parametrize("task", MAIN_TASKS)
def test_each_base_script_has_a_planted_weakness(task, tmp_path):
    out = _run_script(BASE, task, tmp_path / "out.csv")
    assert not out.exists() or _rows(out) != _rows(ANSWERS / f"{task}.csv")


@pytest.mark.parametrize("task", MAIN_TASKS)
def test_the_known_fix_produces_the_answer(task, tmp_path):
    fixed = tmp_path / "fixed"
    shutil.copytree(BASE, fixed)
    for fix in FIXES:
        path = fixed / fix.script
        path.write_text(fix.apply(path.read_text()))
    out = _run_script(fixed, task, tmp_path / "out.csv")
    assert _rows(out) == _rows(ANSWERS / f"{task}.csv")


@pytest.fixture(scope="module")
def bench_rows(tmp_path_factory):
    return bench.run(tmp_path_factory.mktemp("bench"))


def test_every_task_goes_from_wrong_to_right(bench_rows):
    assert [r.base_correct for r in bench_rows] == [False] * 5
    assert [r.final_correct for r in bench_rows] == [True] * 5


def test_each_task_saves_a_lesson_and_the_library_grows(bench_rows):
    assert all(r.lesson for r in bench_rows)
    assert [r.library_before for r in bench_rows] == [0, 1, 2, 3, 4]


def test_budget_at_k1_is_4_runs_and_3_sessions(bench_rows):
    assert {(r.rollouts, r.sessions) for r in bench_rows} == {(4, 3)}


def test_score_is_never_called_inside_the_loop(tmp_path, monkeypatch):
    """The wall: if anything in Harness² or our coach scored a run mid-loop, this raises."""

    def forbidden(self, run_dir, task_id):
        raise AssertionError("score() was called before selection finished")

    monkeypatch.setattr(DataAdapter, "score", forbidden)
    with pytest.raises(AssertionError, match="before selection"):
        bench.run(tmp_path / "out", ["orders-join"])  # the loop finishes; only bench scores
    assert (tmp_path / "out/library/agg/data-engineering/harnesses/orders-join").is_dir()


def test_answer_files_never_reach_an_editor(tmp_path):
    bench.run(tmp_path / "out", ["null-revenue"])
    evidence = [p for p in (tmp_path / "out/runs").rglob("*") if p.is_file()]
    assert evidence and not any("answers" in p.parts for p in evidence)


def test_shared_blind_spot_then_library_fix(tmp_path):
    rows, log = blind_spot.run(tmp_path / "out")
    a, b, c = rows
    assert (a.final_correct, a.lesson) == (False, "")  # no contrast, no lesson
    assert b.final_correct and b.lesson  # one curious editor creates the contrast
    assert c.final_correct  # a blind editor fixed by reading the library
    assert [(e["task"], e["why"]) for e in log] == [
        ("orders-join-b", "curious"),
        ("orders-join-c", "library"),
    ]
