# Architecture — herdr-rtk-savings

## Purpose

A [Herdr](https://herdr.dev) plugin that renders RTK ([Rust Token
Killer](https://github.com/dhamidi/rtk)) token-savings gauges in the Herdr spaces
sidebar — one row per workspace, scoped to the project its panes actually run in.
Each row shows a savings rate (gauge/percent over a window, default: today) and the
number of tokens saved, with color escalation and a lifetime-total fallback when a
project has no RTK activity in the window. A single-file, stdlib-only Python daemon
reads RTK's own history database read-only, once a minute, and publishes rows via the
`herdr` CLI. No network call, no `rtk` subprocess, no telemetry.

## Stack

- Python 3, standard library only (`sqlite3`, `fcntl`, `json`, `subprocess`,
  `signal`, `shutil`, `datetime`, …) — no runtime dependencies.
- Packaging via `pyproject.toml`; source module is `monitor` (`monitor.py`).
- Tooling: Ruff (lint/format), mypy (typecheck), pytest + coverage. Makefile is
  tagged `makefile-tier: lib` — a host-run Python library; tools are invoked through
  `python -m` and degrade gracefully when absent, with CI as the authoritative gate.
- Runtime targets: `platforms = ["linux"]` (macOS untested); requires Herdr ≥ 0.7.0
  and `python3` on `PATH`.

## Layout

- `monitor.py` — the entire application: daemon loop, RTK DB queries, rendering, and
  the herdr CLI integration (single file, stdlib only).
- `herdr-plugin.toml` — Herdr plugin manifest: actions, event hooks, and the popup pane.
- `tests/test_monitor.py` — pytest suite (coverage source is `monitor`).
- `scripts/` — `gen_context_files.py` (context-file generation) and
  `quality_gate.py` (quality gate; excluded from Ruff).
- `.github/` — CI, dependabot, labeler, CODEOWNERS, PR template.
- `graphify-out/` — generated knowledge-graph artifacts (graph.json/html, GRAPH_REPORT.md).
- Root docs & config: `README.md`, `AGENTS.md`, `CLAUDE.md`, `ai-instructions.md`,
  `CHANGELOG.md`, `cliff.toml`, `GitVersion.yml`, `.pre-commit-config.yaml`.

## Entrypoints

`monitor.py` is a CLI dispatched by subcommand (wired from `herdr-plugin.toml`):

- `ensure` — start the background monitor if not already running (used by event hooks).
- `daemon` — the monitor loop itself (spawned by `ensure`).
- `stop` — stop the monitor and clear the sidebar tokens.
- `popup` — detail view for `herdr plugin pane open`.

Manifest wiring: actions `start`/`stop` (workspace context); events
`workspace.created`, `pane.created`, `workspace.focused` → `ensure`; popup pane
`savings` → `popup`. Auto-starts on session activity and stops itself when the Herdr
server goes away.

## Data & external dependencies

- **RTK history DB**: `~/.local/share/rtk/history.db`, opened read-only. Per-project
  stats use the `(project_path, timestamp)` index with a subtree prefix match, so a
  workspace row covers the project and its worktrees.
- **`herdr` CLI**: `herdr pane list` (pane cwds → workspace root = majority cwd) and
  `herdr workspace report-metadata` (publishes rows with a 20-minute TTL).
- **Sidebar tokens**: cannot carry ANSI colors, so the plugin reports one of four
  variants (`rtk`, `rtk_low`, `rtk_hi`, `rtk_sum`) and the user's herdr config styles
  each row.
- **State**: only a pidfile (keyed by `HERDR_PLUGIN_STATE_DIR`); optional per-plugin
  `config.json` (e.g. `min_commands`).

## Build & test

Commands from the `Makefile` (host-run; tools degrade gracefully if absent, CI is
authoritative):

```bash
make install-dev   # install package with dev extras
make dev           # editable install for local dev
make lint          # ruff check monitor tests
make format-check  # ruff format --check
make typecheck     # mypy
make test          # pytest
make test-cov      # pytest with coverage
make build         # python -m build (wheel + sdist)
make pre-commit    # pre-commit run --all-files
make ci            # lint + typecheck + test
```

Install into Herdr: `herdr plugin link ~/Documents/perso/projects/chrysa/herdr-rtk-savings`.
