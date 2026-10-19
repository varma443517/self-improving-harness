# self-improving-harness

Experiments with **recursive agent harnessing**: a strong *coach* model rewrites the prompts,
skills, scripts and memory around a frozen *worker* model, tests every change by running it,
and saves evidence-backed lessons for the next task. No answer key is involved.

It's built on [Harness²](https://github.com/google-research/harness2) from Google Research
([paper](https://arxiv.org/abs/2610.14224)), pinned to an exact commit. Everything here runs
offline on a laptop with no model and no API keys.

![Harness² inner and outer loop](assets/two-loops.svg)

```bash
make install      # uv sync: Harness² (pinned) + pytest + ruff
make demo         # Harness²'s offline demo, both recursion modes
make experiment   # an editor that breaks the harness on purpose
make test         # the experiment as assertions
```

## The idea in four sentences

An agent is a model plus a **harness**: system prompt, guardrails, memory, tool guidance,
subagents, skills, scripts and plugins. Harness² treats that harness as a folder of files an LLM
can edit. For each task, editors **propose** changes, every candidate is **probed** by running
it on the same task, and a composer **composes** the changes that made a visible difference.
After the task, a reflector writes a lesson (cue, lesson, evidence) into a per-domain
**library** that the next task's editors read first.

Two editor roles run side by side and stay in their own lane:

| | INV editor: how the agent *works* | DOM editor: what an *expert* knows |
|---|---|---|
| Fixes | tool errors, repeated mechanical steps, ignored rules | missing domain checks, deliverable structure |
| Usual form | `scripts/check_x.py`, a fallback-and-stop rule | a skill with a trigger |

## What the offline demo shows

The demo task: sum a ledger of signed amounts. The starting harness has a bug: its script only
adds positive amounts. Here are the answers from `make demo` (`--k 2`; *agg* is parallel
recursion, *c* is sequential):

| task | ledger | correct | base harness | candidates (inv, dom) | finals (agg / c) |
|---|---|---|---|---|---|
| ledger-1 | 100.25, −20.10, 5.00 | 85.15 | **105.25** ✗ | 85.15 | 85.15 |
| ledger-2 | 35.50, −10.25, −5.00 | 20.25 | **35.50** ✗ | 20.25 | 20.25 |

- **Budget:** 28 executions and 32 editor calls for 2 tasks. Parallel and sequential get the
  same number of runs per task (4k), so wide vs deep is a fair comparison.
- **The lesson it saved** after ledger-1:
  *cue:* "When a ledger includes credits and debits" · *lesson:* "Include both signs when
  summing" · *evidence:* the probe total included the credits the base run omitted.
- **The library is advice, not a patch.** ledger-2 still started from the original, broken
  harness (35.50). The lesson guided its editors, and the fix had to be shown to help again.

## Experiment: when the editor breaks the harness

[`experiments/broken_edit.py`](experiments/broken_edit.py) makes two editors delete the one script
the agent needs. `inv1` does it on both attempts; `dom1` only on the first.

```
Rejections sent back to the editor:
  dom1.a2: systemprompt.md invokes `scripts/summarize.py` but that file is not in the harness
  inv1.a2: systemprompt.md invokes `scripts/summarize.py` but that file is not in the harness

stage  attempts  fell back  answer
base1         0  False      Total: 105.25
inv1          2  True       Total: 105.25
dom1          2  False      Total: 85.15
agg1          1  False      Total: 85.15
```

Every proposed harness is validated before it runs. A rejected edit gets **one retry**, with the
reason pasted into the prompt, and the editor repairs its own rejected files rather than
starting over. If the retry fails too, the stage keeps the harness it started from. A failed
editor costs a turn, not the result: the composition still picked up `dom1`'s fix.

## Notes from the paper worth knowing

- **Coach and worker are different models.** The frozen executors are Gemini 3.5 Flash and
  GLM-5; the editor, composer, selector and reflector are Claude Opus 4.8. "Frozen model" means
  the worker. Improving it takes a capable coach, and that coach is part of the bill.
- **A weaker model with a better harness can beat a stronger one.** On WorkBuddy-Bench (OpenCode)
  one improvement step took GLM-5 from 64.2 to 75.7, above Gemini 3.5 Flash's unimproved 72.4.
- **Every part earns its place** (one step, Gemini 3.5 Flash, OpenCode):

  | removed | WorkBuddy-Bench | JobBench |
  |---|---|---|
  | nothing (full method) | 77.5 | 36.0 |
  | the library | 74.4 | 34.2 |
  | INV/DOM scoping | 74.6 | 32.3 |
  | composition | 75.9 | 34.1 |

- **Agents will find the answer key if they can.** The repo's docs report a Codex rollout that
  downloaded its own task's grading rubric without being told to (JobBench publishes its rubrics
  on Hugging Face). The code keeps answer
  keys and grader output out of the *editors'* context, but the executor's network is open:
  block benchmark hosts at the firewall.
- **Where it fails:** the blind selector sometimes prefers a weaker final (55 over 95 in one
  case), and a wrong premise shared by every candidate leaves nothing to contrast, so it spreads
  instead of getting fixed.

## Roadmap

- **Data-engineering tasks:** a Harness² adapter for SQL and pipeline work (a join that drops
  rows, CSV deduplication, schema drift), each with a starting harness that has a known weakness.
- **A real coach:** run the same tasks with an LLM editor and compare base vs refined, and
  parallel vs sequential, with the cost of each.
- **Where it breaks, on purpose:** a shared blind spot (every candidate keeps the same wrong
  `INNER JOIN`, so no lesson is written) and a cost ledger per task.

## Credits and licence

Harness² is by Xu, Chen, CuiZhu, Dalvi Mishra, Ming, Yu, Han, Lee and Pfister at Google Research,
released under Apache-2.0. This repository installs it as a dependency and doesn't vendor its
code. The code and text here are MIT-licensed; see [LICENSE](LICENSE).
