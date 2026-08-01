# herdr-rtk-savings

[RTK](https://github.com/dhamidi/rtk) (Rust Token Killer) token-savings gauges in the
[Herdr](https://herdr.dev) spaces sidebar — one row per workspace, scoped to the project
its panes actually run in.

```
● doc-gen
  main  ✚2
  ▰▰▰▰▰▰▰▰▱▱ 85% ·4.2M
```

- **Gauge / percent** = savings rate over the window (default: today), **number** = tokens saved.
- Row color escalates with efficiency: red under 40%, yellow up to 80%, green above.
- A project with no RTK activity in the window falls back to its lifetime total:

```
∑ 57% ·18M
```

- `prefix+alt+r` (optional keybinding below) opens a detail popup: today / 7 days / lifetime
  meters per workspace, plus the timestamp of the last command RTK recorded.

Numbers match `rtk gain -p` exactly — same database, same arithmetic.

## How it works

- A single-file, stdlib-only Python daemon reads RTK's own history database
  (`~/.local/share/rtk/history.db`) **read-only**, once a minute.
- Per-project stats use the `(project_path, timestamp)` index with a subtree prefix match,
  so a workspace row covers the project and its worktrees (~100 ms per query).
- Pane cwds come from `herdr pane list`; the workspace root is the majority cwd of its panes.
- Rows are published per workspace with `herdr workspace report-metadata` and a 20-minute TTL,
  so stale data disappears on its own if the monitor dies.
- Sidebar tokens cannot carry ANSI colors, so the plugin reports one of four token variants
  (`rtk`, `rtk_low`, `rtk_hi`, `rtk_sum`) and your config styles each row — that is what
  makes the color dynamic.
- No network call, no `rtk` subprocess, no telemetry, no state beyond a pidfile.

## Install

```bash
herdr plugin link ~/Documents/perso/projects/chrysa/herdr-rtk-savings
```

Add the gauge rows to `~/.config/herdr/config.toml` (the plugin reports exactly one of the
four variants per space; rows without a token are skipped, so spaces without RTK data stay
compact):

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace"],
  ["branch", "git_status"],
  [{ token = "$rtk", fg = "#f9e2af" }],
  [{ token = "$rtk_low", fg = "#f38ba8" }],
  [{ token = "$rtk_hi", fg = "#a6e3a1", bold = true }],
  [{ token = "$rtk_sum", fg = "#6c7086" }],
]
```

Optional popup keybinding:

`prefix+r` is taken by the built-in resize mode, so bind the popup elsewhere:

```toml
[[keys.command]]
key = "prefix+alt+r"
type = "shell"
command = '"$HERDR_BIN_PATH" plugin pane open --plugin chrysa.rtk-savings --entrypoint savings'
```

Reload and kick off the monitor once:

```bash
herdr server reload-config
herdr plugin action invoke start --plugin chrysa.rtk-savings
```

After that it auto-starts on session activity (workspace/pane creation events) and stops
itself when the Herdr server goes away.

## Configuration

Optional `config.json` in the plugin config dir (`herdr plugin config-dir` prints it,
typically `~/.config/herdr/plugins/config/chrysa.rtk-savings/`):

```json
{
  "db_path": "~/.local/share/rtk/history.db",
  "window": "today",
  "min_commands": 20
}
```

- `db_path` — RTK history database.
- `window` — `today`, `24h`, `7d`, or `all` (the gauge window; `all` never falls back).
- `min_commands` — below this many commands in the window, the row shows the lifetime total,
  so a handful of early-morning commands never renders a meaningless rate.

Restart the monitor after editing (`stop` + `start` actions).

## Requirements

- Herdr ≥ 0.7.0, macOS or Linux, `python3` in `PATH`
- RTK installed and recording (`rtk gain` must show data)

If RTK stops recording, rows freeze on the lifetime total (`∑`) — the popup's
"last recorded command" line is the tell.

## Credits

Structure mirrors [houser.claude-usage](https://github.com/iamhouser/herdr-claude-usage-multi),
which pioneered the sidebar-token gauge approach.

## License

MIT
