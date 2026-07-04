# AGENTS.md — Briefly

Solo vibe-coding project. Local audio-briefing tool for macOS (Apple Silicon).
Provider abstraction for LLM/TTS — see CLAUDE.md for architecture.

## Scope
- Implement only what was asked. No unrequested refactors or architecture changes.
- Smallest change that achieves the goal.
- Avoid spawning subagents for small tasks — free tier quota is limited, keep it single-agent unless the task genuinely needs parallel work.

## Code
- Python 3.12+, type hints on new function signatures
- New config values go in config.yaml, never hardcoded
- No new dependencies without a one-line reason in the commit message
- No TODOs/placeholders in merged code — finish it or open a GitHub issue

## Tests
- New features need tests in tests/
- Run `pytest` before every commit; fix red tests yourself, don't commit around them
- Don't touch existing tests unless the behavior change is intentional

## Docs
- Update README.md only when user-visible behavior changes

## Git (solo project, no reviewer)
- Commit and push directly to main — no PR workflow
- Conventional commits (feat:, fix:, chore:, docs:), one logical change per commit
- Run pytest green before pushing

## Tradeoffs
- Maintainability over cleverness
- Respect existing architecture (provider abstraction) over faster shortcuts
