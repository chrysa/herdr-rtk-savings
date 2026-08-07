"""Unit tests for the herdr-rtk-savings monitor.

Cover the pure logic (window math, subtree prefix queries, fallback rules,
rendering) and the daemon plumbing (pidfile lock, publish round, dispatch)
without touching a real herdr server or the RTK history database on disk.
"""
import json
import os
import sqlite3
import sys
import types
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monitor  # noqa: E402


# --------------------------------------------------------------- fixtures --

@pytest.fixture
def db():
    """In-memory `commands` table shaped like RTK's history schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE commands ("
        "project_path TEXT, input_tokens INTEGER, "
        "saved_tokens INTEGER, timestamp TEXT)"
    )
    yield conn
    conn.close()


def add(conn, path, sent, saved, ts="2999-01-01T00:00:00+00:00"):
    conn.execute(
        "INSERT INTO commands VALUES (?, ?, ?, ?)", (path, sent, saved, ts)
    )
    conn.commit()


class FakeProc:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


# ------------------------------------------------------------ herdr_bin --

def test_herdr_bin_explicit_executable(monkeypatch, tmp_path):
    exe = tmp_path / "herdr"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("HERDR_BIN_PATH", str(exe))
    assert monitor.herdr_bin() == str(exe)


def test_herdr_bin_deleted_suffix_stripped(monkeypatch, tmp_path):
    exe = tmp_path / "herdr"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("HERDR_BIN_PATH", f"{exe} (deleted)")
    assert monitor.herdr_bin() == str(exe)


def test_herdr_bin_falls_back_to_which(monkeypatch):
    monkeypatch.delenv("HERDR_BIN_PATH", raising=False)
    monkeypatch.setattr(monitor.shutil, "which", lambda _: "/somewhere/herdr")
    assert monitor.herdr_bin() == "/somewhere/herdr"


def test_herdr_bin_last_resort_bare_name(monkeypatch):
    monkeypatch.delenv("HERDR_BIN_PATH", raising=False)
    monkeypatch.setattr(monitor.shutil, "which", lambda _: None)
    monkeypatch.setattr(monitor.os, "access", lambda *a, **k: False)
    assert monitor.herdr_bin() == "herdr"


# ------------------------------------------------------------ load_config --

def test_load_config_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "CONFIG_DIR", str(tmp_path))
    cfg = monitor.load_config()
    assert cfg["window"] == "today"
    assert cfg["min_commands"] == 20


def test_load_config_merges_file(monkeypatch, tmp_path):
    (tmp_path / "config.json").write_text(
        json.dumps({"window": "7d", "min_commands": 5, "db_path": "~/x.db"})
    )
    monkeypatch.setattr(monitor, "CONFIG_DIR", str(tmp_path))
    cfg = monitor.load_config()
    assert cfg["window"] == "7d"
    assert cfg["min_commands"] == 5
    assert cfg["db_path"] == os.path.expanduser("~/x.db")


# ------------------------------------------------------------ window_start --

def test_window_start_all_is_none():
    assert monitor.window_start("all") is None
    assert monitor.window_start("weird") is None


@pytest.mark.parametrize("window", ["today", "24h", "7d"])
def test_window_start_returns_utc_iso(window):
    cutoff = monitor.window_start(window)
    assert cutoff.endswith("+00:00")
    parsed = datetime.fromisoformat(cutoff)
    assert parsed.tzinfo == timezone.utc


def test_window_start_today_is_midnight_local():
    cutoff = datetime.fromisoformat(monitor.window_start("today"))
    local_midnight = cutoff.astimezone()
    assert (local_midnight.hour, local_midnight.minute, local_midnight.second) == (0, 0, 0)


# ------------------------------------------------------------ query_project --

def test_query_project_exact_and_subtree(db):
    add(db, "/home/p", 100, 40)
    add(db, "/home/p/sub", 50, 30)
    add(db, "/home/other", 999, 999)
    commands, sent, saved = monitor.query_project(db, "/home/p", None)
    assert (commands, sent, saved) == (2, 150, 70)


def test_query_project_prefix_does_not_match_sibling(db):
    # /home/p must not swallow /home/paste
    add(db, "/home/p", 10, 5)
    add(db, "/home/paste", 100, 100)
    commands, sent, saved = monitor.query_project(db, "/home/p", None)
    assert (commands, sent, saved) == (1, 10, 5)


def test_query_project_since_filters(db):
    add(db, "/home/p", 10, 5, ts="2000-01-01T00:00:00+00:00")
    add(db, "/home/p", 20, 10, ts="2999-01-01T00:00:00+00:00")
    commands, sent, saved = monitor.query_project(db, "/home/p", "2500-01-01T00:00:00+00:00")
    assert (commands, sent, saved) == (1, 20, 10)


def test_query_project_empty(db):
    assert monitor.query_project(db, "/nope", None) == (0, 0, 0)


# ------------------------------------------------------------ stats_for --

def test_stats_for_uses_window_when_enough_commands(db, monkeypatch):
    monkeypatch.setitem(monitor.CONFIG, "min_commands", 2)
    for _ in range(3):
        add(db, "/home/p", 100, 50)
    stats = monitor.stats_for(db, "/home/p", "all")  # window "all" -> since None
    assert stats["scope"] == "all"  # window "all" reports as all anyway
    assert stats["commands"] == 3


def test_stats_for_falls_back_to_lifetime_below_min(db, monkeypatch):
    monkeypatch.setitem(monitor.CONFIG, "min_commands", 10)
    add(db, "/home/p", 100, 50, ts="2000-01-01T00:00:00+00:00")
    stats = monitor.stats_for(db, "/home/p", "7d")
    assert stats["scope"] == "all"
    assert stats["commands"] == 1


def test_stats_for_window_scope_when_qualified(db, monkeypatch):
    monkeypatch.setitem(monitor.CONFIG, "min_commands", 1)
    add(db, "/home/p", 100, 50)  # ts far future -> inside any window
    stats = monitor.stats_for(db, "/home/p", "7d")
    assert stats["scope"] == "7d"


def test_stats_for_none_when_no_data(db):
    assert monitor.stats_for(db, "/home/empty", "today") is None


# ------------------------------------------------------------ compact --

@pytest.mark.parametrize(
    "tokens,expected",
    [
        (0, "0"),
        (999, "999"),
        (1500, "1.5K"),
        (15000, "15K"),
        (2_100_000, "2.1M"),
        (18_400_000, "18M"),
        (3_000_000_000, "3.0G"),
    ],
)
def test_compact(tokens, expected):
    assert monitor.compact(tokens) == expected


# ------------------------------------------------------------ render --

def test_render_lifetime_sum():
    variant, text = monitor.render({"scope": "all", "saved": 18_400_000, "sent": 32_857_142})
    assert variant == "rtk_sum"
    assert text.startswith("∑ 56% ")


def test_render_high_variant():
    variant, text = monitor.render({"scope": "today", "saved": 90, "sent": 100})
    assert variant == "rtk_hi"
    assert "90%" in text
    assert "▰" in text


def test_render_low_variant():
    variant, _ = monitor.render({"scope": "today", "saved": 10, "sent": 100})
    assert variant == "rtk_low"


def test_render_plain_variant():
    variant, _ = monitor.render({"scope": "today", "saved": 60, "sent": 100})
    assert variant == "rtk"


def test_render_gauge_capped():
    _, text = monitor.render({"scope": "today", "saved": 100, "sent": 100})
    assert text.count("▰") == monitor.GAUGE_CELLS


# ------------------------------------------------------------ map_workspaces --

def test_map_workspaces_majority_vote():
    panes = [
        {"workspace_id": "w1", "cwd": "/a"},
        {"workspace_id": "w1", "cwd": "/a"},
        {"workspace_id": "w1", "cwd": "/b"},
        {"workspace_id": "w2", "foreground_cwd": "/c"},
    ]
    assert monitor.map_workspaces(panes) == {"w1": "/a", "w2": "/c"}


def test_map_workspaces_skips_paneless_cwd():
    panes = [{"workspace_id": "w1", "cwd": ""}]
    assert monitor.map_workspaces(panes) == {}


# ------------------------------------------------------------ herdr_json --

def test_herdr_json_parses_result_key(monkeypatch):
    monkeypatch.setattr(
        monitor, "herdr_cli",
        lambda *a: FakeProc(stdout=json.dumps({"result": {"panes": [1, 2]}})),
    )
    assert monitor.herdr_json("pane", "list", key="panes") == [1, 2]


def test_herdr_json_raises_on_failure(monkeypatch):
    monkeypatch.setattr(
        monitor, "herdr_cli", lambda *a: FakeProc(stderr="boom", returncode=1)
    )
    with pytest.raises(RuntimeError, match="boom"):
        monitor.herdr_json("pane", "list", key="panes")


# ------------------------------------------------- report / clear variants --

def test_report_variant_publishes_and_clears_others(monkeypatch):
    captured = {}
    monkeypatch.setattr(monitor, "herdr_cli", lambda *a: captured.update(args=a))
    monitor.report_variant("w1", "rtk_hi", "gauge")
    args = captured["args"]
    assert "--token" in args and "rtk_hi=gauge" in args
    # every other variant is cleared
    for name in monitor.VARIANTS:
        if name != "rtk_hi":
            idx = args.index(name)
            assert args[idx - 1] == "--clear-token"


def test_clear_variants_clears_all(monkeypatch):
    captured = {}
    monkeypatch.setattr(monitor, "herdr_cli", lambda *a: captured.update(args=a))
    monitor.clear_variants("w1")
    for name in monitor.VARIANTS:
        assert name in captured["args"]


# ------------------------------------------------------------ meter / popup --

def test_meter_color_thresholds():
    assert "\033[32m" in monitor.meter(90)
    assert "\033[33m" in monitor.meter(50)
    assert "\033[31m" in monitor.meter(10)


def test_popup_line_none_without_tokens(db):
    add(db, "/home/p", 0, 0)
    assert monitor.popup_line(db, "/home/p", "all") is None


def test_popup_line_renders(db):
    add(db, "/home/p", 100, 50)
    line = monitor.popup_line(db, "/home/p", "all")
    assert "50%" in line
    assert "saved" in line


def test_popup_project_reports_no_activity(db, capsys):
    monitor.popup_project(db, "label", "/home/empty")
    assert "no RTK activity" in capsys.readouterr().out


def test_popup_project_lists_windows(db, capsys):
    add(db, "/home/p", 100, 50)
    monitor.popup_project(db, "label", "/home/p")
    out = capsys.readouterr().out
    assert "Lifetime" in out


def test_popup_frame_handles_unreachable_herdr(db, capsys, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(monitor, "herdr_json", boom)
    monitor.popup_frame(db)
    assert "not reachable" in capsys.readouterr().out


def test_popup_frame_renders_projects(db, capsys, monkeypatch):
    add(db, "/home/p", 100, 50)
    monkeypatch.setattr(
        monitor, "herdr_json",
        lambda *a, key: {"panes": [{"workspace_id": "w1", "cwd": "/home/p"}],
                         "workspaces": [{"workspace_id": "w1", "label": "Proj"}]}[key],
    )
    monitor.popup_frame(db)
    out = capsys.readouterr().out
    assert "Proj" in out
    assert "last recorded command" in out


# ------------------------------------------------------------ pidfile lock --

def _isolate_state(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "STATE_DIR", str(tmp_path))
    monkeypatch.setattr(monitor, "PIDFILE", str(tmp_path / "monitor.pid"))


def test_running_pid_missing(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    assert monitor.running_pid() is None


def test_running_pid_reads_value(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    (tmp_path / "monitor.pid").write_text("4321\n")
    assert monitor.running_pid() == 4321


def test_daemon_alive_false_without_pidfile(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    assert monitor.daemon_alive() is False


def test_claim_and_detect_lock(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    lock = monitor.claim_pidfile()
    assert lock is not None
    # while held, a second claim fails and the daemon reads as alive
    assert monitor.claim_pidfile() is None
    assert monitor.daemon_alive() is True
    assert monitor.running_pid() == os.getpid()
    lock.close()
    # released -> no longer alive
    assert monitor.daemon_alive() is False


# ------------------------------------------------------------ publish_round --

def test_publish_round_publishes_then_clears(db, monkeypatch):
    add(db, "/home/p", 100, 50)
    monkeypatch.setitem(monitor.CONFIG, "min_commands", 1)
    monkeypatch.setitem(monitor.CONFIG, "window", "all")

    state = {"has_pane": True}

    def fake_json(*a, key):
        if key == "panes":
            return [{"workspace_id": "w1", "cwd": "/home/p"}] if state["has_pane"] else []
        return [{"workspace_id": "w1"}]

    reports = []
    clears = []
    monkeypatch.setattr(monitor, "herdr_json", fake_json)
    monkeypatch.setattr(monitor, "report_variant", lambda ws, v, t: reports.append((ws, v, t)))
    monkeypatch.setattr(monitor, "clear_variants", lambda ws: clears.append(ws))

    published = {}
    assert monitor.publish_round(db, published) is True
    assert reports and "w1" in published

    # second round, unchanged -> no new report
    reports.clear()
    monitor.publish_round(db, published)
    assert reports == []

    # pane goes away -> workspace is cleared and forgotten
    state["has_pane"] = False
    monitor.publish_round(db, published)
    assert clears == ["w1"]
    assert "w1" not in published


# ------------------------------------------------------------ cmd_* --

def test_cmd_ensure_skips_when_alive(monkeypatch):
    monkeypatch.setattr(monitor, "daemon_alive", lambda: True)
    called = []
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *a, **k: called.append(a))
    monitor.cmd_ensure()
    assert called == []


def test_cmd_ensure_spawns_when_dead(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(monitor, "daemon_alive", lambda: False)
    called = []
    monkeypatch.setattr(monitor.subprocess, "Popen", lambda *a, **k: called.append(a))
    monitor.cmd_ensure()
    assert called


def test_cmd_stop_kills_and_clears(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    (tmp_path / "monitor.pid").write_text("999999")
    monkeypatch.setattr(monitor, "daemon_alive", lambda: True)
    killed = []
    monkeypatch.setattr(monitor.os, "kill", lambda pid, sig: killed.append((pid, sig)))
    monkeypatch.setattr(monitor, "herdr_json", lambda *a, key: [{"workspace_id": "w1"}])
    cleared = []
    monkeypatch.setattr(monitor, "clear_variants", lambda ws: cleared.append(ws))
    monitor.cmd_stop()
    assert killed == [(999999, monitor.signal.SIGTERM)]
    assert cleared == ["w1"]


def test_cmd_stop_survives_herdr_failure(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    monkeypatch.setattr(monitor, "daemon_alive", lambda: False)

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(monitor, "herdr_json", boom)
    monitor.cmd_stop()  # must not raise


def test_main_dispatches(monkeypatch):
    calls = []
    monkeypatch.setattr(monitor, "cmd_stop", lambda: calls.append("stop"))
    monkeypatch.setattr(sys, "argv", ["monitor.py", "stop"])
    monitor.main()
    assert calls == ["stop"]


def test_main_defaults_to_ensure(monkeypatch):
    calls = []
    monkeypatch.setattr(monitor, "cmd_ensure", lambda: calls.append("ensure"))
    monkeypatch.setattr(sys, "argv", ["monitor.py"])
    monitor.main()
    assert calls == ["ensure"]


# ------------------------------------------------------------ cmd_daemon --

def test_cmd_daemon_exits_when_lock_taken(monkeypatch):
    monkeypatch.setattr(monitor, "claim_pidfile", lambda: None)
    # returns immediately without touching the db
    monkeypatch.setattr(monitor, "open_db", lambda p: (_ for _ in ()).throw(AssertionError))
    monitor.cmd_daemon()


class _Lock:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_cmd_daemon_breaks_after_repeated_db_failures(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    (tmp_path / "monitor.pid").write_text("")
    lock = _Lock()
    monkeypatch.setattr(monitor, "claim_pidfile", lambda: lock)
    monkeypatch.setattr(monitor, "SOCKET_PATH", "")
    monkeypatch.setattr(monitor.time, "sleep", lambda _s: None)

    def boom(_path):
        raise RuntimeError("db gone")
    monkeypatch.setattr(monitor, "open_db", boom)
    monitor.cmd_daemon()
    assert lock.closed is True


def test_cmd_daemon_breaks_on_sustained_socket_absence(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    lock = _Lock()
    monkeypatch.setattr(monitor, "claim_pidfile", lambda: lock)
    monkeypatch.setattr(monitor, "SOCKET_PATH", str(tmp_path / "missing.sock"))
    monkeypatch.setattr(monitor.time, "sleep", lambda _s: None)
    opened = []
    monkeypatch.setattr(monitor, "open_db", lambda p: opened.append(p))
    monitor.cmd_daemon()
    assert opened == []  # never got past the socket gate
    assert lock.closed is True


def test_cmd_daemon_one_successful_round_then_stop(monkeypatch, tmp_path):
    _isolate_state(monkeypatch, tmp_path)
    lock = _Lock()
    monkeypatch.setattr(monitor, "claim_pidfile", lambda: lock)
    monkeypatch.setattr(monitor, "SOCKET_PATH", "")

    class _StopLoop(Exception):
        pass

    calls = {"n": 0}

    def fake_sleep(_s):
        calls["n"] += 1
        raise _StopLoop
    monkeypatch.setattr(monitor.time, "sleep", fake_sleep)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(monitor, "open_db", lambda p: _Conn())
    monkeypatch.setattr(monitor, "publish_round", lambda conn, pub: True)
    with pytest.raises(_StopLoop):
        monitor.cmd_daemon()
    assert calls["n"] == 1


# ------------------------------------------------------------ cmd_popup --

def test_cmd_popup_renders_then_exits(monkeypatch):
    class _StopLoop(Exception):
        pass

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(monitor, "open_db", lambda p: _Conn())
    monkeypatch.setattr(monitor, "popup_frame", lambda conn: None)

    def fake_sleep(_s):
        raise _StopLoop
    monkeypatch.setattr(monitor.time, "sleep", fake_sleep)
    with pytest.raises(_StopLoop):
        monitor.cmd_popup()


def test_cmd_popup_handles_db_error(monkeypatch, capsys):
    class _StopLoop(Exception):
        pass

    def boom(_p):
        raise RuntimeError("no db")
    monkeypatch.setattr(monitor, "open_db", boom)

    def fake_sleep(_s):
        raise _StopLoop
    monkeypatch.setattr(monitor.time, "sleep", fake_sleep)
    with pytest.raises(_StopLoop):
        monitor.cmd_popup()
    assert "unavailable" in capsys.readouterr().out


# ------------------------------------------------------------ open_db --

def test_open_db_read_only(tmp_path):
    path = tmp_path / "h.db"
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE commands (project_path TEXT, input_tokens INT, "
                 "saved_tokens INT, timestamp TEXT)")
    conn.commit()
    conn.close()
    ro = monitor.open_db(str(path))
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("INSERT INTO commands VALUES ('x', 1, 1, 't')")
    ro.close()


def test_module_has_expected_variants():
    assert isinstance(monitor.VARIANTS, tuple)
    assert types.FunctionType  # sanity import guard
