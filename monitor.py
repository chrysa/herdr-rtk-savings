#!/usr/bin/env python3
"""herdr-rtk-savings - RTK token-savings gauges in the Herdr spaces sidebar.

Every workspace row shows how many tokens RTK (Rust Token Killer) saved for the
project its panes actually run in:

    ▰▰▰▰▰▰▰▱▱▱ 69% ·2.1M

(gauge/percent = savings rate over the window, number = tokens saved). Row color
escalates with efficiency: dim under 40%, plain up to 80%, bold green above.
A project with no RTK activity in the window falls back to its lifetime total:

    ∑ 56% ·18.4M

Data comes from RTK's own history database (~/.local/share/rtk/history.db),
opened read-only. No `rtk` subprocess per workspace, no network, no telemetry.

Commands:
  ensure  start the background monitor if not already running (event hooks use this)
  daemon  the monitor loop itself (spawned by ensure)
  stop    stop the monitor and clear the sidebar tokens
  popup   detail view for `herdr plugin pane open`
"""
import fcntl
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

PLUGIN_ID = "chrysa.rtk-savings"
SOURCE = f"plugin:{PLUGIN_ID}"

DEFAULT_DB = "~/.local/share/rtk/history.db"
POLL_S = 60  # local sqlite read; cheap, but savings barely move minute-to-minute
TTL_MS = POLL_S * 20 * 1000  # tokens outlive a few failed reads, then expire
REFRESH_S = 600  # re-report unchanged tokens well before the TTL expires
GAUGE_CELLS = 10
LOW_PCT, HIGH_PCT = 40, 80
VARIANTS = ("rtk", "rtk_low", "rtk_hi", "rtk_sum")  # each styled by its own sidebar row

def herdr_bin():
    """Absolute path to the herdr CLI.

    Plugin commands do not inherit the user's login PATH, so a bare "herdr"
    raises FileNotFoundError and the daemon would quit after a few ticks.
    """
    # herdr exports HERDR_BIN_PATH from /proc/self/exe, which reads
    # "/path/to/herdr (deleted)" once the binary has been replaced by an
    # in-place upgrade - trust it only when it actually resolves.
    explicit = os.environ.get("HERDR_BIN_PATH")
    if explicit and os.access(explicit, os.X_OK):
        return explicit
    if explicit and explicit.endswith(" (deleted)"):
        stripped = explicit[: -len(" (deleted)")]
        if os.access(stripped, os.X_OK):
            return stripped
    found = shutil.which("herdr")
    if found:
        return found
    for candidate in ("~/.local/bin/herdr", "/usr/local/bin/herdr",
                      "/opt/homebrew/bin/herdr", "/usr/bin/herdr"):
        path = os.path.expanduser(candidate)
        if os.access(path, os.X_OK):
            return path
    return "herdr"


HERDR = herdr_bin()
SOCKET_PATH = os.environ.get("HERDR_SOCKET_PATH", "")
STATE_DIR = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser(
    f"~/.local/state/{PLUGIN_ID}")
CONFIG_DIR = os.environ.get("HERDR_PLUGIN_CONFIG_DIR") or os.path.expanduser(
    f"~/.config/herdr/plugins/config/{PLUGIN_ID}")
PIDFILE = os.path.join(STATE_DIR, "monitor.pid")


def load_config():
    """Optional <config dir>/config.json: db_path, window ("today"|"24h"|"7d"|"all")."""
    # min_commands keeps an early-morning handful of commands from rendering a
    # statistically meaningless rate; below it the row shows the lifetime total.
    settings = {"db_path": DEFAULT_DB, "window": "today", "min_commands": 20}
    try:
        with open(os.path.join(CONFIG_DIR, "config.json"), encoding="utf-8") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    settings["db_path"] = os.path.expanduser(settings["db_path"])
    return settings


CONFIG = load_config()


# ---------------------------------------------------------------------- rtk --

def window_start(window):
    """UTC ISO cutoff for a window name, or None for the whole history.

    RTK stores timestamps as UTC ISO-8601 with a `+00:00` offset, so a plain
    string comparison against a same-shaped cutoff is a correct range filter
    and lets sqlite use the (project_path, timestamp) index.
    """
    now = datetime.now().astimezone()
    if window == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif window == "24h":
        start = now - timedelta(hours=24)
    elif window == "7d":
        start = now - timedelta(days=7)
    else:
        return None
    return start.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def open_db(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)


def query_project(conn, root, since):
    """(commands, input_tokens, saved_tokens) for one project subtree."""
    sql = ("SELECT COUNT(*), COALESCE(SUM(input_tokens), 0), "
           "COALESCE(SUM(saved_tokens), 0) FROM commands "
           "WHERE (project_path = ? OR substr(project_path, 1, ?) = ?)")
    params = [root, len(root) + 1, root + os.sep]
    if since:
        sql += " AND timestamp >= ?"
        params.append(since)
    return conn.execute(sql, params).fetchone()


def stats_for(conn, root, window):
    """Window stats for a project, with the lifetime total as fallback."""
    commands, sent, saved = query_project(conn, root, window_start(window))
    if commands >= CONFIG["min_commands"] and sent:
        return {"scope": window, "commands": commands, "sent": sent, "saved": saved}
    commands, sent, saved = query_project(conn, root, None)
    if not commands or not sent:
        return None
    return {"scope": "all", "commands": commands, "sent": sent, "saved": saved}


# ------------------------------------------------------------------- herdr --

def herdr_cli(*args):
    return subprocess.run([HERDR, *args], capture_output=True, text=True, timeout=10)


def herdr_json(*args, key):
    proc = herdr_cli(*args)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"herdr {' '.join(args)} failed")
    return json.loads(proc.stdout)["result"][key]


def map_workspaces(panes):
    """workspace_id -> project root, by majority vote over pane cwds."""
    tallies = {}
    for pane in panes:
        cwd = pane.get("cwd") or pane.get("foreground_cwd") or ""
        if not cwd:
            continue
        tally = tallies.setdefault(pane["workspace_id"], {})
        tally[cwd] = tally.get(cwd, 0) + 1
    return {ws: max(tally, key=tally.get) for ws, tally in tallies.items() if tally}


def report_variant(workspace_id, variant, text):
    """Publish one variant and retract the others, in a single CLI call."""
    args = ["workspace", "report-metadata", workspace_id, "--source", SOURCE,
            "--ttl-ms", str(TTL_MS), "--token", f"{variant}={text}"]
    for name in VARIANTS:
        if name != variant:
            args += ["--clear-token", name]
    herdr_cli(*args)


def clear_variants(workspace_id):
    args = ["workspace", "report-metadata", workspace_id, "--source", SOURCE]
    for name in VARIANTS:
        args += ["--clear-token", name]
    herdr_cli(*args)


# --------------------------------------------------------------- rendering --

def compact(tokens):
    for limit, suffix in ((1e9, "G"), (1e6, "M"), (1e3, "K")):
        if tokens >= limit:
            value = tokens / limit
            return f"{value:.1f}{suffix}" if value < 10 else f"{value:.0f}{suffix}"
    return str(int(tokens))


def render(stats):
    """(variant, text) for one project's savings."""
    pct = round(100 * stats["saved"] / stats["sent"])
    if stats["scope"] == "all":
        return "rtk_sum", f"∑ {pct}% ·{compact(stats['saved'])}"
    variant = "rtk_hi" if pct >= HIGH_PCT else "rtk_low" if pct < LOW_PCT else "rtk"
    filled = min(GAUGE_CELLS, round(GAUGE_CELLS * pct / 100))
    gauge = "▰" * filled + "▱" * (GAUGE_CELLS - filled)
    return variant, f"{gauge} {pct}% ·{compact(stats['saved'])}"


# ------------------------------------------------------------------ daemon --

def running_pid():
    try:
        return int(open(PIDFILE).read().strip())
    except Exception:
        return None


def daemon_alive():
    """True when a monitor holds the pidfile lock.

    The lock, not the pid, is the authority: pids are recycled fast enough on a
    busy machine that a stale pidfile regularly points at an unrelated live
    process, and `ensure` would then never restart a dead monitor.
    """
    if not os.path.exists(PIDFILE):
        return False
    try:
        with open(PIDFILE, "a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(handle, fcntl.LOCK_UN)
        return False
    except OSError:
        return True


def cmd_ensure():
    if daemon_alive():
        return
    os.makedirs(STATE_DIR, exist_ok=True)
    # check-then-spawn has a tiny race; a duplicate daemon exits on its first tick
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "daemon"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def publish_round(conn, published):
    """One refresh pass over every workspace. Returns False when herdr is gone."""
    panes = herdr_json("pane", "list", key="panes")
    workspaces = herdr_json("workspace", "list", key="workspaces")
    roots = map_workspaces(panes)
    now = time.monotonic()
    for workspace in workspaces:
        ws_id = workspace["workspace_id"]
        root = roots.get(ws_id)
        stats = stats_for(conn, root, CONFIG["window"]) if root else None
        if stats:
            variant, text = render(stats)
            prev = published.get(ws_id)
            if not prev or prev[:2] != (variant, text) or now - prev[2] > REFRESH_S:
                report_variant(ws_id, variant, text)
                published[ws_id] = (variant, text, now)
        elif ws_id in published:
            clear_variants(ws_id)
            del published[ws_id]
    return True


def claim_pidfile():
    """Exclusive daemon slot, or None when another daemon already holds it.

    The pid check in `ensure` races when two events fire together, so the
    winner is decided here by an flock the loser cannot take.
    """
    os.makedirs(STATE_DIR, exist_ok=True)
    handle = open(PIDFILE, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def cmd_daemon():
    lock = claim_pidfile()
    if not lock:
        return
    published = {}  # workspace_id -> (variant, text, monotonic_ts)
    failures = 0
    socket_misses = 0
    while True:
        if SOCKET_PATH and not os.path.exists(SOCKET_PATH):
            # a config reload re-creates the socket, so only a sustained
            # absence means the herdr server is really gone
            socket_misses += 1
            if socket_misses >= 3:
                break
            time.sleep(10)
            continue
        socket_misses = 0
        try:
            with open_db(CONFIG["db_path"]) as conn:
                publish_round(conn, published)
            failures = 0
        except Exception:
            failures += 1
            if failures >= 3:
                break
            time.sleep(10)
            continue
        time.sleep(POLL_S)
    lock.close()
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


def cmd_stop():
    pid = running_pid() if daemon_alive() else None
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        for workspace in herdr_json("workspace", "list", key="workspaces"):
            clear_variants(workspace["workspace_id"])
    except Exception:
        pass
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


# ------------------------------------------------------------------- popup --

RESET, DIM, BOLD = "\033[0m", "\033[2m", "\033[1m"
WINDOWS = (("Today", "today"), ("7 days", "7d"), ("Lifetime", "all"))


def meter(pct, width=28):
    filled = min(width, round(width * pct / 100))
    tint = "\033[32m" if pct >= HIGH_PCT else "\033[33m" if pct >= LOW_PCT else "\033[31m"
    return f"{tint}{'█' * filled}{DIM}{'·' * (width - filled)}{RESET}"


def popup_line(conn, root, window):
    commands, sent, saved = query_project(conn, root, window_start(window))
    if not sent:
        return None
    pct = round(100 * saved / sent)
    return f"{meter(pct)} {pct:>3}%  {compact(saved):>7} saved  {DIM}{commands} cmd{RESET}"


def popup_project(conn, label, root):
    print()
    print(f"  {BOLD}{label}{RESET}  {DIM}{root}{RESET}")
    empty = True
    for title, window in WINDOWS:
        line = popup_line(conn, root, window)
        if line:
            empty = False
            print(f"    {title:9}{line}")
    if empty:
        print(f"    {DIM}no RTK activity recorded for this path{RESET}")


def popup_frame(conn):
    sys.stdout.write("\033[2J\033[H")
    print(f"{BOLD} RTK token savings{RESET}  {DIM}{CONFIG['db_path']}{RESET}")
    try:
        panes = herdr_json("pane", "list", key="panes")
        workspaces = herdr_json("workspace", "list", key="workspaces")
    except Exception:
        print("\n  herdr is not reachable.")
        return
    roots = map_workspaces(panes)
    labels = {w["workspace_id"]: w.get("label") or w["workspace_id"] for w in workspaces}
    for ws_id, root in sorted(roots.items(), key=lambda kv: labels.get(kv[0], "")):
        popup_project(conn, labels.get(ws_id, ws_id), root)
    print()
    latest = conn.execute("SELECT MAX(timestamp) FROM commands").fetchone()[0]
    print(f"{DIM} last recorded command: {latest or 'never'}{RESET}")


def cmd_popup():
    while True:
        try:
            with open_db(CONFIG["db_path"]) as conn:
                popup_frame(conn)
        except Exception as err:
            sys.stdout.write("\033[2J\033[H")
            print(f" RTK history database unavailable: {err}")
        print(f"{DIM} refreshes every 30s - close the popup to exit{RESET}")
        sys.stdout.flush()
        time.sleep(30)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "ensure"
    {"ensure": cmd_ensure, "daemon": cmd_daemon,
     "stop": cmd_stop, "popup": cmd_popup}.get(command, cmd_ensure)()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
