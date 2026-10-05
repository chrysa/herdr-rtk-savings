# REVIEW — documentation pass notes

> Output of a docs-only documentation pass (no source/tests/config/CI changed). Records what
> was created, what was skipped, contradictions, and documentation debt for the owner.

## Files created (root-level Markdown only)

- `ARCHITECTURE.md` — purpose, runtime shape, command surface, control flow, variant model,
  resilience decisions, layout, constraints.
- `TESTING.md` — suite location, run commands, CI, coverage status.
- `SECURITY.md` — secret-scan result, attack surface, data sensitivity, owner actions.
- `DECISIONS.md` — six reconstructed ADRs + referenced external ADRs.
- `GLOSSARY.md` — domain terms.
- `REVIEW.md` — this file.

## Docs intentionally skipped (with reason)

- **PRD / TRD / REQUIREMENTS** — SKIPPED. The README already reads as a de-facto product+design
  spec for a small single-purpose plugin; a separate PRD/TRD/requirements matrix would duplicate
  it without adding verifiable REQ-* traceability. No issue tracker or spec source exists in-repo
  to anchor requirements against.
- **CONSTRAINTS** — SKIPPED as a standalone file; constraints are captured in ARCHITECTURE.md.
- **OBSERVABILITY** — SKIPPED. The plugin has "no network, no telemetry, no state beyond a
  pidfile" (FACT); there is no observability surface to document beyond the self-expiring TTL
  rows already covered in ARCHITECTURE/DECISIONS.
- **ROADMAP** — SKIPPED. No committed roadmap, milestones, or open backlog found in-repo; the
  only forward-looking notes are `platforms` macOS-untested (manifest) and the quality-gate
  "no baseline yet" (Makefile). Inventing a roadmap would violate the no-fabrication rule.

## Contradictions / inconsistencies flagged (owner to resolve)

1. **`CLAUDE.md` is an unfilled template.** It still contains `[PROJECT_NAME]`,
   `[PLACEHOLDER]` values, `Stack: [Python 3.14 / Node.js LTS / React / ...]`,
   `Test coverage: [X]%`, and instructions to "read `primer.md` FIRST" — but no `primer.md`
   exists at the repo root, and the project is a stdlib-Python herdr plugin, not React/Node.
   The chrysa managed standards block below it is populated; the top template header is not.
   ACTION: fill or trim the `CLAUDE.md` template header to match the real project.
2. **Default-branch mismatch.** `CLAUDE.md` / standards say the default branch is `develop`;
   the working tree is currently on `chore/claude-config-drift-hook` (feature branch, expected).
   Not a defect — noted for orientation.
3. **`herdr-plugin.toml` version 0.1.0 vs README "MIT" and no release tag.** CHANGELOG shows
   only `[Unreleased]`. Versioning source of truth is `GitVersion.yml` + git cliff; the manifest
   pins `0.1.0`. INFERENCE: pre-first-release. Confirm the intended released version before tagging.

## Documentation debt

- Coverage percentage is unstated (TESTING.md, UNKNOWN) — fill once `make test` output is known.
- Quality-gate baseline is not configured for this repo (Makefile prints SKIP) — a baseline
  would make `make` gating meaningful.
- macOS support is declared untested in the manifest — validate or keep the caveat.

## Method / integrity

- No source, tests, dependencies, CI, or config were modified. No files deleted. No commits,
  pushes, or PRs. Only root Markdown docs were created.
- Claims are tagged FACT / INFERENCE / UNKNOWN / PROPOSAL. No secret values reproduced;
  secret-scan result is in SECURITY.md.
- `.claude/rules/` does not exist in this repo, so nothing was written there.
- `CLAUDE.md` was left untouched (its template header needs owner input, and the managed
  standards block must not be edited by this pass).
