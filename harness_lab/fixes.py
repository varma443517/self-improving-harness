"""The five planted weaknesses, and the edit a good harness editor should make for each.

A real coach model would have to *discover* these edits by reading the task, the transcripts
and the scripts. Our scripted coach (coach.py) knows them in advance, so every run is free and
repeatable. That makes the experiments about Harness²'s loop, not about one model's luck.

Each fix belongs to one editor lane, matching Harness²'s split:
  INV = how the agent works (procedure, robustness)   DOM = what a practitioner knows
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fix:
    id: str
    lane: str  # "INV" or "DOM"
    script: str  # harness-relative path of the script this fix edits
    edits: tuple[tuple[str, str], ...]  # (old text, new text) pairs, applied in order
    change: str  # one line for the reflector's edit table
    cue: str  # when the lesson applies -- the library's trigger
    lesson: str  # what to do when the cue matches

    def applied_to(self, text: str) -> bool:
        """True when every new text is already present: the fix is in this script."""
        return all(new in text for _, new in self.edits)

    def apply(self, text: str) -> str:
        """Return the script with this fix applied; unchanged if the old text is missing."""
        for old, new in self.edits:
            if old in text:
                text = text.replace(old, new, 1)
        return text


FIXES: tuple[Fix, ...] = (
    Fix(
        id="join",
        lane="DOM",
        script="scripts/join_report.py",
        edits=(("    JOIN orders o ON", "    LEFT JOIN orders o ON"),),
        change="INNER JOIN -> LEFT JOIN, so customers without orders stay in the report",
        cue="When a report must list every customer, including ones with no orders",
        lesson="Drive the report from customers with a LEFT JOIN and default missing totals to 0.",
    ),
    Fix(
        id="dedupe",
        lane="INV",
        script="scripts/dedupe_events.py",
        edits=(('subset=["event_id"]', 'subset=["user", "action", "ts"]'),),
        change="deduplicate on the business key (user, action, ts) instead of event_id",
        cue="When an event log contains events resent with a new event_id",
        lesson="Deduplicate on the business key (user, action, timestamp), not the transport id.",
    ),
    Fix(
        id="drift",
        lane="INV",
        script="scripts/load_daily.py",
        edits=(
            (
                "src, out = Path(sys.argv[1]), Path(sys.argv[2])\n",
                "src, out = Path(sys.argv[1]), Path(sys.argv[2])\n"
                'ALIASES = {"amount_usd": "amount"}  # upstream renames we have seen\n',
            ),
            (
                "        for row in csv.DictReader(f):\n",
                "        for row in csv.DictReader(f):\n"
                "            row = {ALIASES.get(k, k): v for k, v in row.items()}\n",
            ),
        ),
        change="map known column aliases (amount_usd -> amount) before reading rows",
        cue="When a daily file arrives with a renamed column",
        lesson="Map known column aliases to the canonical name before reading any row.",
    ),
    Fix(
        id="nulls",
        lane="DOM",
        script="scripts/revenue_stats.py",
        edits=(
            (
                'revenue = sales["revenue"].fillna(0)',
                'revenue = sales["revenue"]  # unknown is not zero; mean() skips blanks',
            ),
        ),
        change="stop filling blanks with 0; average the known values and count the blanks",
        cue="When a numeric column has blank values",
        lesson="Treat blanks as unknown, not zero: average the known values, report the count.",
    ),
    Fix(
        id="tz",
        lane="DOM",
        script="scripts/daily_counts.py",
        edits=(
            (
                'sales["day"] = ts.dt.date',
                'sales["day"] = ts.dt.tz_convert(meta["timezone"]).dt.date',
            ),
        ),
        change="convert UTC timestamps to the store's time zone before taking the date",
        cue="When counting events per business day for a store",
        lesson="Convert UTC timestamps to the store's time zone before taking the date.",
    ),
)

BY_ID = {fix.id: fix for fix in FIXES}
