# SECURITY — herdr-rtk-savings

> Docs-only pass. This file **reports** posture and findings for the owner; it does not
> change code. No secret values are reproduced here.

## Secret scan (FACT)

- No hardcoded secrets, API keys, tokens, or passwords were found in `monitor.py` or the
  `scripts/` tooling. The only matches for secret-related terms are inside
  `scripts/quality_gate.py`, which *invokes* `detect-secrets scan` and parses its count —
  i.e. security tooling, not embedded credentials.
- `scripts/gen_context_files.py` contains a French policy string reminding never to hardcode
  a secret/key/token/machine path — documentation text, not a secret.

No HIGH/CRITICAL secret-exposure finding for the owner.

## Attack surface (FACT / INFERENCE)

- [FACT] No network I/O: README and module docstring state "no network, no telemetry".
- [FACT] The RTK history DB is opened **read-only** (`open_db`, `monitor.py`); the plugin
  never writes to RTK data.
- [FACT] The plugin shells out to the `herdr` CLI (`herdr_cli`/`herdr_json`, `monitor.py`)
  and resolves the binary defensively (`herdr_bin`), including stripping a stale
  ` (deleted)` suffix from `/proc/self/exe`.
- [INFERENCE] Command construction uses argv lists (`command = ["python3", "monitor.py", ...]`
  in `herdr-plugin.toml`; `herdr_cli(*args)`), not shell strings — lower shell-injection risk.
  A full review of every subprocess call site is out of scope for this docs-only pass.
- [FACT] It reads a SQLite DB path derived from the operator's home and config
  (`load_config`, `monitor.py`). SQL is parameterised at the query layer (`query_project`);
  the DB path itself is operator-controlled, not attacker-controlled. LOW concern.

## Data sensitivity (INFERENCE)

The plugin surfaces per-project token-savings counts and last-command timestamps on the
local sidebar only. It exposes RTK usage metadata for the operator's own machine; there is
no PII beyond local project paths and no outbound transmission.

## Owner action items

- None at HIGH/CRITICAL severity from this pass.
- [PROPOSAL] If a subprocess/argument-handling security review is desired, run
  `/security-review` on the diff or delegate to the Senior SecOps agent (per global CLAUDE.md);
  this pass is documentation-only and did not perform a code-level SAST review.
