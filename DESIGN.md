# herdr-rtk-savings — Design contract

> Contract for the two terminal surfaces of this herdr plugin: the savings gauge on each
> space row of the herdr sidebar, and the detail popup. Read it before changing what the
> plugin prints or how it is styled; update it in the same change. Status:
> **[implemented]** links the code · **[decided]** names the decision · **[proposed]** is not
> agreed. This file documents the current surface; it does not redesign it.

## 1. Surface and status

- **Surface:** terminal UI hosted by herdr — sidebar tokens published per workspace and a
  popup pane. No web or graphical UI. **[implemented]** ([monitor.py](monitor.py),
  [herdr-plugin.toml](herdr-plugin.toml))
- **Lifecycle:** shipped, version 0.1.0 in [herdr-plugin.toml](herdr-plugin.toml); Linux only
  (macOS untested, so not claimed).
- **Detailed specs:** none. Behaviour and configuration: [README.md](README.md); decisions:
  [DECISIONS.md](DECISIONS.md).

## 2. Users, devices and priority tasks

| User | Context and device | Priority tasks (three at most) |
| --- | --- | --- |
| Developer running agents through RTK in herdr | Linux terminal, sidebar always visible, popup on demand | read a workspace's savings rate at a glance · compare today, 7 days and lifetime · notice that RTK stopped recording |

Primary action: in the sidebar, read the rate of the current workspace; in the popup, find the
workspace block and its *Today* line.

## 3. Journeys and navigation

- **J1 — Glance:** each space row shows `▰▰▰▰▰▰▰▱▱▱ 69% ·2.1M` (rate over the window, tokens
  saved), or `∑ 56% ·18.4M` (lifetime) when the window has fewer than `min_commands`
  commands. A workspace without data shows no row. **[implemented]** (`render` in
  [monitor.py](monitor.py))
- **J2 — Detail:** a keybinding opens the popup (70 % × 45 %): one block per workspace with
  *Today*, *7 days* and *Lifetime* meters, then the last recorded command time; it redraws every
  30 s until closed. **[implemented]** (`cmd_popup` in [monitor.py](monitor.py))
- **J3 — Set up:** link the plugin, add the four styled rows to the herdr config, invoke
  *start*; optional `config.json` (`db_path`, `window`, `min_commands`). The monitor restarts
  itself on workspace and pane events. **[implemented]** ([README.md](README.md))
- **Information architecture:** one token variant per workspace (`rtk`, `rtk_low`, `rtk_hi`,
  `rtk_sum`), each styled by its own sidebar row (ADR-0003 in [DECISIONS.md](DECISIONS.md),
  **[decided]**); popup blocks sorted by workspace label.
- **Density:** compact — one sidebar line per workspace; three lines per popup block.

## 4. Identity

No brand, logo or palette of its own: colour in the sidebar belongs to the user's herdr config.
The signature element is the ten-cell gauge glyph (`▰`/`▱`) next to a percentage. The
sidebar-token gauge pattern follows `houser.claude-usage` (credited in the README); no code or
asset was copied.

## 5. Tokens and components (owned elsewhere)

| Concern | Source of truth | Rules of use |
| --- | --- | --- |
| Sidebar colours | the user's `~/.config/herdr/config.toml` (example rows in [README.md](README.md)) | one `fg` per variant; the plugin never sends ANSI in tokens |
| Popup colours | `meter`, `RESET`, `DIM`, `BOLD` in [monitor.py](monitor.py) | 16-colour ANSI: green ≥ 80 %, yellow ≥ 40 %, red below |
| Thresholds and gauge | `LOW_PCT`, `HIGH_PCT`, `GAUGE_CELLS` in [monitor.py](monitor.py) | 40 / 80 %, ten cells |
| Numbers | `compact` in [monitor.py](monitor.py) | K / M / G suffixes, one decimal below 10 |
| Timing | `POLL_S`, `TTL_MS`, `REFRESH_S` in [monitor.py](monitor.py) | read every 60 s, tokens expire after 20 min, re-report every 600 s |
| Popup size | `[[panes]]` in [herdr-plugin.toml](herdr-plugin.toml) | 70 % wide, 45 % high |

- **Shared contract:** `contract.css` and `@chrysa/ui` do not apply to a terminal surface.
- **Design drift:** the module docstring says the row is "dim under 40%, plain up to 80%, bold
  green above", the README example says red, yellow, green; the popup colours are hard-coded and
  cannot follow the user's theme.

## 6. Interaction and states

- **Action feedback:** *start* and *stop* actions; *stop* clears every token. **[implemented]**
- **Forms:** none; configuration is a JSON file read at start.
- **Data states:**

  | State | Where it appears | Behaviour |
  | --- | --- | --- |
  | Loading | popup | first frame after a local read; no loading text |
  | Empty | sidebar, popup | no row for a workspace without data; `no RTK activity recorded for this path` |
  | Error | popup | `herdr is not reachable.`; `RTK history database unavailable: <error>` |
  | Offline / backend unreachable | sidebar | the monitor exits after repeated database or socket failures; rows expire with the TTL |
  | Stale data | sidebar, popup | lifetime fallback marked `∑`; popup shows `last recorded command: <ISO time>`; the sidebar has no age cue |
  | Reconnect | sidebar | `ensure` re-arms the monitor on `workspace.created`, `pane.created`, `workspace.focused` |

- **Real-time:** herdr replaces each token in place. The popup clears and redraws every 30 s;
  blocks below its height are cut (no scroll).
- **Motion:** none (FE-053, terminal: no animation).

## 7. Responsive and support conventions

Sidebar text is about 20 characters wide. Popup lines are about 75 columns (meter fixed at 28
cells), so a popup narrower than that wraps. Plugin commands run without the login `PATH`: the
herdr binary is resolved defensively (ADR-0006). The README suggests `prefix+alt+r` for the
popup; [herdr-cockpit](https://github.com/chrysa/herdr-cockpit) binds `prefix+ctrl+r` and avoids
`alt` chords.

## 8. Accessibility

- **Target:** terminal readability; meaning never by colour alone.
- **Perception:** the rate is always a number next to the gauge; the lifetime fallback is the
  `∑` symbol, not a colour. **[implemented]**
- **Keyboard:** the popup has no keys of its own; herdr closes it.
- **Gaps:** `NO_COLOR` is not honoured in the popup; counts such as `1527 cmd` have no
  thousands separator (canon display rule); the time is a raw UTC ISO string; no screen-reader
  pass.

## 9. Assets

None: no fonts, icons or images are shipped. Glyphs are Unicode characters. Repository code:
[MIT](LICENSE).

## 10. Acceptance criteria and evidence

- **Criteria:** every sidebar row carries a rate and an amount; the variant follows the 40 / 80
  thresholds and `∑` marks the lifetime fallback; figures match `rtk gain -p`; the popup names
  its empty and error states; no row appears for a workspace without data. Covered by
  `test_render_*`, `test_popup_*` and `test_query_project_*` in
  [tests/test_monitor.py](tests/test_monitor.py).
- **Evidence log:**

  | Date | Change | Checks run (tool, sizes, modes) | Result | Not run, and why |
  | --- | --- | --- | --- | --- |
  | 2026-11-08 | contract written from the code | source review | gaps listed in §11 | no terminal run: documentation-only change |

## 11. Open choices, known gaps and maintenance

- **Open choices:**
  - **[proposed]** honour `NO_COLOR` and size the popup meter from the terminal width.
  - **[proposed]** group thousands with a narrow no-break space in popup counts.
  - **[proposed]** show the age of the last recorded command ("12 min ago") next to the ISO time.
  - **[proposed]** align the docstring and the README on one colour rule.
- **Known gaps:** a frozen RTK history looks like a valid lifetime total in the sidebar; the
  popup cannot scroll.
- **Maintenance:** owner of this repository. Update this file with any change to printed
  wording, thresholds, token variants or popup layout, and add an evidence row.
