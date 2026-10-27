# One command per job, so the README, tests and future-you all run things the same way.
.PHONY: install demo experiment bench blind-spot test lint fmt

install:          ## create .venv with Harness² (pinned) + dev tools
	uv sync

demo:             ## Harness²'s own offline demo: both recursion modes, no model, no keys
	rm -rf out/demo
	uv run harness2-demo --output out/demo --k 2

experiment:       ## what happens when an editor breaks the harness? (retry, then fallback)
	rm -rf out/broken-edit
	uv run python experiments/broken_edit.py out/broken-edit

bench:            ## five data tasks through Harness², scored only after the loop
	rm -rf out/bench
	uv run python -m harness_lab.bench out/bench

blind-spot:       ## a mistake every editor shares, then a library lesson that fixes it
	rm -rf out/blind-spot
	uv run python experiments/blind_spot.py out/blind-spot

test:             ## the experiments, as assertions -- still no model needed
	uv run pytest -q

lint:             ## style + likely-bug checks
	uv run ruff check .
	uv run ruff format --check .

fmt:              ## auto-fix what ruff can fix
	uv run ruff check --fix .
	uv run ruff format .
