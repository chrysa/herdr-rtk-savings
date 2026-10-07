# GLOSSARY — herdr-rtk-savings

> Terms as used in this repository. FACT unless tagged.

- **Herdr** — the terminal-multiplexer / workspace tool (herdr.dev) whose spaces sidebar this
  plugin decorates. The plugin targets `min_herdr_version = 0.7.0`.
- **RTK (Rust Token Killer)** — https://github.com/dhamidi/rtk. A tool that reduces LLM token
  usage and records what it saved in a local history DB. This plugin reads that DB.
- **History DB** — `~/.local/share/rtk/history.db`, RTK's own SQLite database, opened read-only.
- **Workspace / space** — a herdr workspace; the plugin publishes one gauge row per workspace.
- **Pane** — a terminal pane inside a workspace. The workspace root is the majority cwd of its
  panes (`map_workspaces`).
- **Savings rate / percent** — savings over the window as a percentage; drives the gauge and the
  row's colour variant.
- **Tokens saved** — absolute token count saved in the window (rendered compact, e.g. `18.4M`).
- **Window** — the time span the gauge covers: `today` (default), `24h`, `7d`, or `all`
  (config key `window`).
- **Lifetime fallback** — when a project has no RTK activity in the window (or fewer than
  `min_commands`), the row shows the project's lifetime total instead (the `rtk_sum` variant,
  rendered with a `∑` prefix).
- **Variant** — one of four sidebar tokens (`rtk`, `rtk_low`, `rtk_hi`, `rtk_sum`); the user's
  `config.toml` styles each. Chosen by thresholds `LOW_PCT` / `HIGH_PCT`.
- **`ensure` / `daemon` / `stop` / `popup`** — the `monitor.py` sub-commands (start-if-absent,
  the loop, stop+clear, detail view). See ARCHITECTURE.md.
- **TTL** — token time-to-live (`TTL_MS`, 20 min); rows self-expire if the monitor dies.
- **Pidfile lock** — the file lock that authoritatively signals a live monitor (see ADR-0005).
- **`report-metadata`** — the `herdr workspace report-metadata` CLI call used to publish rows.
- **Generated context files** — `handover.md`, `llms-full.txt`, `context-map.json`,
  `ai-instructions.md`, produced by `scripts/gen_context_files.py` (ADR D-0012); not hand-edited.
