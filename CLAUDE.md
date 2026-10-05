@AGENTS.md

# CLAUDE.md — [PROJECT_NAME]

> Replace [PROJECT_NAME] and all [PLACEHOLDER] values before committing.
> @[claude-sonnet-4-6]

> **Claude Code**: at session start, read `primer.md` FIRST (current state), then this file (conventions).
> Also read `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md` for code specifications.

## Project

**Name:** [PROJECT_NAME]
**Stack:** [Python 3.14 / Node.js LTS / React / ...]
**Purpose:** [One sentence description]

## Conventions

- Language: English — all code, comments, documentation, instructions, and configuration files must be in English.
- Governance: the five strategic pillars and the refutable ADR format are mandatory — see the managed `chrysa:standards` block below (inlined by distribute-standards, Governance section).
- Commits: Conventional Commits (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`)
- Branch naming: `feature/`, `bugfix/`, `chore/`, `hotfix/`, `release/`
- Default branch: `develop`

## Standards

- Max function lines: 50
- Max file lines: 500
- Max complexity (heuristic): 10
- Lint warnings: 0
- Test coverage: [X]%

## Session Workflow

| Step | Command | When |
|------|---------|------|
| Start session | `make prepare` or `/prepare` | Always — loads primer + git context |
| End session | `make hindsight` or `/hindsight` | Always — updates primer + memory |
| Init memory | `make memory-init` | Once per repo |
| Export to Obsidian | `make hindsight OBSIDIAN=<path>` | Optional |

**Files:**
- `primer.md` — current state, next actions, blockers (read before CLAUDE.md)
- `.claude/memory/` — session, decisions, known-issues, progress (not committed except progress/decisions)

## Setup

```bash
make install             # Install dependencies
make memory-init         # Initialize primer.md + .claude/memory/
make lint                # Run linter
make test                # Run tests
make build               # Build (if applicable)
codegraph init --index . # Build CodeGraph index (run once, never commit .codegraph/)
/graphify                # Build knowledge graph (run once or /graphify --update; never commit graphify-out/)
```

## CI

- CI runs on push to `develop`/`main` and on PRs to those branches
- CI must pass before merging
- SonarQube analysis is configured in CI (not via sonar-project.properties)

## Repository-specific rules

[Add project-specific rules here. E.g.:]
- [ ] Describe any project-specific allowlists for secret scanner
- [ ] Describe custom thresholds vs shared defaults
- [ ] Note any hooks that are disabled for this repo and why

## Model-specific notes (@[claude-sonnet-4-6])

[Add any rules or instructions that apply only when using a specific model.]

## Skills

Shared skills from `shared-standards/.claude/skills/`:
- `testing-pytest/SKILL.md` — pytest DDD + pytest-mock + constants (load when writing tests)
- `dockerfile-multistage/SKILL.md` — 4-stage Python 3.14 containers (load when editing Dockerfile)
- `api-design/SKILL.md` — REST standards + FastAPI patterns (load when designing endpoints)
- `ui-ux/SKILL.md` — UX/UI/ergonomics across ALL surfaces (web, CLI, VS Code, Discord, desktop, game, agent) + WCAG 2.1 AA + dark mode + i18n FR+EN (load when building any human-facing surface)

## graphify

Follow the /graphify skill.
