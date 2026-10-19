"""The broken-edit experiment, pinned down as assertions (no model needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))

from broken_edit import run  # noqa: E402

WRONG = "Total: 105.25"  # base harness: sums positive amounts only, skips the -20.10 credit
RIGHT = "Total: 85.15"  # 100.25 - 20.10 + 5.00


def test_bad_edits_are_retried_then_discarded(tmp_path):
    stages, rejections = run(tmp_path / "out")
    by = {s.label: s for s in stages}

    assert by["base1"].answer == WRONG

    # inv1 broke the harness twice: one retry, then it inherits the base harness unchanged.
    assert by["inv1"].fell_back and by["inv1"].attempts == 2
    assert by["inv1"].answer == WRONG
    assert "summarize.py" in rejections["inv1.a2"]

    # dom1 broke it once, was told why, and its second attempt was accepted.
    assert not by["dom1"].fell_back and by["dom1"].attempts == 2
    assert by["dom1"].answer == RIGHT

    # The composition still found the good edit: a failed editor costs a turn, not the result.
    assert by["agg1"].answer == RIGHT
