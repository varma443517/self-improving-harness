# One command per job, so the README, tests and future-you all run things the same way.
.PHONY: install demo experiment test lint fmt

install:          ## create .venv with Harness² (pinned) + dev tools
	uv sync

demo:             ## Harness²'s own offline demo: both recursion modes, no model, no keys
	rm -rf out/demo
	uv run harness2-demo --output out/demo --k 2

experiment:       ## what happens when an editor breaks the harness? (retry, then fallback)
	rm -rf out/broken-edit
	uv run python experiments/broken_edit.py out/broken-edit

test:             ## the experiments, as assertions -- still no model needed
	uv run pytest -q

lint:             ## style + likely-bug checks
	uv run ruff check .
	uv run ruff format --check .

fmt:              ## auto-fix what ruff can fix
	uv run ruff check --fix .
	uv run ruff format .
