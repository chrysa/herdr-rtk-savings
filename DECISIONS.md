# DECISIONS — herdr-rtk-savings

> Docs-only pass. ADRs reconstructed from code and README evidence. Where rationale is not
> written down, status/context is tagged UNKNOWN. These are descriptive, not new mandates.

## ADR-0001 — Single-file, stdlib-only daemon

- **Status:** Accepted (INFERENCE — reflected in the shipped `monitor.py`).
- **Context:** The plugin runs on any Linux box where herdr runs, without a Python install step.
- **Decision:** Implement the whole plugin as one stdlib-only `monitor.py`; `pyproject.toml`
  declares only dev tooling (pytest/coverage/ruff), no runtime deps.
- **Consequence:** No virtualenv/pip needed at runtime; simple to `herdr plugin link`. Trades
  richer structure for a single ~418-line module.

## ADR-0002 — Read RTK's history DB directly, read-only

- **Status:** Accepted (FACT — `open_db`, README "How it works").
- **Context:** Alternative would be spawning `rtk` per workspace, which is slow and couples to
  RTK's CLI output (RTK's `ps` proxy can even filter matches — README gotcha).
- **Decision:** Open `~/.local/share/rtk/history.db` read-only and query the
  `(project_path, timestamp)` index with a subtree prefix match (~100 ms/query).
- **Consequence:** No subprocess per workspace, worktrees covered by the prefix match; couples
  to RTK's on-disk schema instead of its CLI.

## ADR-0003 — Four styled token variants instead of ANSI colour

- **Status:** Accepted (FACT — `VARIANTS`, README).
- **Context:** Sidebar tokens cannot carry ANSI colour.
- **Decision:** Emit exactly one of `rtk` / `rtk_low` / `rtk_hi` / `rtk_sum` per workspace and
  let the user's `config.toml` style each row.
- **Consequence:** Colour lives in user config; rows without a token are skipped, so spaces
  without RTK data stay clean.

## ADR-0004 — TTL + periodic re-report for self-healing rows

- **Status:** Accepted (FACT — `TTL_MS`, `REFRESH_S`, `POLL_S` in `monitor.py`).
- **Decision:** Publish tokens with a 20-minute TTL and re-report unchanged tokens every
  600 s; poll every 60 s.
- **Consequence:** If the monitor dies, stale rows expire on their own without cleanup.

## ADR-0005 — Pidfile lock is the liveness authority

- **Status:** Accepted (FACT — `daemon_alive` docstring, `claim_pidfile`).
- **Decision:** Treat the pidfile *lock*, not the stored pid, as authoritative for "is a
  monitor alive", because pids recycle and a stale pidfile can point at a live unrelated process.
- **Consequence:** `ensure` reliably restarts a dead monitor. Gotcha (README): a herdr-launched
  monitor and a manual `python3 monitor.py ensure` use different pidfiles/locks — start via herdr.

## ADR-0006 — Defensive `herdr` binary resolution

- **Status:** Accepted (FACT — `herdr_bin`, README gotcha).
- **Decision:** Validate `HERDR_BIN_PATH`, strip a stale ` (deleted)` suffix (from
  `/proc/self/exe` after in-place upgrade), fall back to `PATH` and standard install locations.
- **Consequence:** Survives herdr in-place upgrades that would otherwise `FileNotFoundError`.

## Referenced external ADRs (FACT)

- **D-0012** — generated context files (`handover.md`, `llms-full.txt`, `context-map.json`,
  `ai-instructions.md` are produced by `scripts/gen_context_files.py`; do not hand-edit).
  Full text lives in chrysa shared-standards, not this repo.
- Chrysa transverse standards (governance, SCM, architecture, testing, containers, etc.) are
  inlined into `CLAUDE.md` and `standards/rules/`; the refutable ADR format is mandated there.

## UNKNOWN

- No repo-local `DECISIONS.md`/ADR directory pre-existed; the above are reconstructed. Any
  formally recorded rationale (dates, alternatives weighed) is UNKNOWN beyond code comments.
