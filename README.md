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

The popup, one block per workspace:

```
 RTK token savings  ~/.local/share/rtk/history.db

  guideline-checker  ~/projects/chrysa/guideline-checker
    Today    ····························   1%        1 saved  5 cmd
    7 days   ███████████████·············  53%      30K saved  162 cmd
    Lifetime █████████████████···········  62%     779K saved  1527 cmd

  homeassistant-config  ~/projects/chrysa/homeassistant-config
    Today    ██████████████████··········  64%     1.3K saved  17 cmd
    7 days   █████████████████···········  61%     5.8K saved  70 cmd
    Lifetime ████████████████████········  70%      15K saved  102 cmd

 last recorded command: 2026-08-01T16:12:04.481+00:00
```

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

## Troubleshooting

- **Rows never appear, monitor dies after ~30 s.** herdr sets `HERDR_BIN_PATH` from
  `/proc/self/exe`, which reads `/path/to/herdr (deleted)` once herdr has been upgraded
  in place. Every CLI call then fails with `FileNotFoundError`. The plugin already works
  around it (it validates the path, strips the ` (deleted)` suffix, then falls back to
  `PATH` and the usual install locations) — but any other plugin spawning `herdr` from
  that variable will silently stop. Restarting the herdr server clears the stale path.
- **`ps | grep` shows no daemon while it is running.** If RTK's Claude Code hook is
  active, `ps` output goes through RTK's filter and the match can be dropped. Use
  `rtk proxy ps -eo pid,etime,cmd` for the raw output.
- **Two daemons at once.** They are keyed by `HERDR_PLUGIN_STATE_DIR`, which herdr sets
  and a manual `python3 monitor.py ensure` does not — the two use different pidfiles and
  therefore different locks. Start the monitor through herdr, not by hand.

## Requirements

- Herdr ≥ 0.7.0, `python3` in `PATH`
- RTK installed and recording (`rtk gain` must show data)

Linux only for now. Nothing in the code is platform-specific — it is stdlib, a read-only
sqlite open and the herdr CLI — but it has never been run on macOS, so the manifest does
not claim it. If you try it there, say so and it goes back in.

If RTK stops recording, rows freeze on the lifetime total (`∑`) — the popup's
"last recorded command" line is the tell.

## Credits

Structure mirrors [houser.claude-usage](https://github.com/iamhouser/herdr-claude-usage-multi),
which pioneered the sidebar-token gauge approach.

## License

MIT
