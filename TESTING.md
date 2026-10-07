# TESTING — herdr-rtk-savings

> Docs-only pass. Commands below are transcribed from `Makefile` / `pyproject.toml`;
> they were not executed by this pass (no code/tests were run or modified).

## Test suite (FACT)

- Framework: **pytest** with **pytest-cov** and **pytest-mock** style monkeypatching.
  Config in `pyproject.toml` under `[tool.pytest.ini_options]` and `[tool.coverage.*]`
  (`source = ["monitor"]`, `branch = true`).
- Location: `tests/test_monitor.py` (~600 lines), covering the single module `monitor.py`.
- Observed test names (`grep "def test_"`), e.g.:
  - `test_herdr_json_raises_on_failure`
  - `test_cmd_stop_survives_herdr_failure`
  - `test_cmd_daemon_breaks_after_repeated_db_failures`
  INFERENCE: tests exercise CLI dispatch, herdr-CLI failure handling, DB-failure backoff,
  and the daemon loop — consistent with the resilience behaviour documented in the README.

## How to run (FACT — from `Makefile`)

| Target | Effect |
|--------|--------|
| `make install` | Install tooling / dependencies. |
| `make lint`    | `ruff check monitor.py tests` (falls back to `ruff` on PATH). |
| `make test`    | `pytest --cov=monitor --cov-report=term-missing`. |
| `make check`   | Runs `pre-commit run --all-files` when available (skips if not installed — "runs in CI"). |

INFERENCE: because the runtime is stdlib-only, the suite can run under a bare Python
with pytest installed; no service or DB fixture beyond what the tests construct in `tmp_path`.

## Coverage (UNKNOWN)

- A `.coverage` file and `.benchmarks/` exist in the tree, but no coverage percentage is
  asserted in committed config. The `CLAUDE.md` "Test coverage: [X]%" placeholder is unfilled
  (see REVIEW.md). Actual coverage figure: UNKNOWN without running `make test`.

## CI (FACT)

- `.github/workflows/ci.yml` runs on pushes to `feat/**`, `fix/**`, `chore/**`, `ci/**`
  branches (and PRs) and produces a coverage artifact consumed by a separate SonarQube job
  (comment in `ci.yml`). Full gating semantics: see the workflow file.
- Quality gate: `scripts/quality_gate.py` exists; `make` quality-gate target currently prints
  "no baseline configured for this repo yet" / "SKIP (no baseline recorded)" (FACT, `Makefile`).
  So the numeric quality gate is not yet enforced locally for this repo.

## Verification status of this document (FACT)

Commands are transcribed, not run. To verify: `make test` and `make lint` from the repo root.
