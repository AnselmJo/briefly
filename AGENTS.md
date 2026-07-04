cd /Users/aj/projekte/briefly
cat > AGENTS.md << 'EOF'
# AGENTS.md — Briefly

Solo vibe-coding project by one developer, no reviewers, no other users.
Personal morning-assistant podcast tool ("Daily Cast"), runs fully local
on macOS (Windows support planned). Segment-based episodes: greeting,
weather, calendar, news, inbox/book notes, affirmation, fun fact.
Architecture uses a provider abstraction for LLM (Ollama) and TTS (Piper).

## Project map (avoid re-discovering this every session)
- Config system: src/briefly/config.py (Pydantic models + load_config/save_config)
- Config template: config/config.example.yaml
- CLI entrypoint + error handling: src/briefly/cli.py (_load_config_or_exit)
- Web app: src/briefly/web/app.py
- Tests mirror src/ 1:1 in tests/
- Run only the relevant test file while iterating: `.venv/bin/pytest tests/test_config.py`
  Run the full suite only once, right before committing.

## Autonomy — you have full permission
- You are fully authorized to create, edit, and delete files, run any
  command, install dependencies, and commit and push directly to GitHub.
- Do not ask for confirmation on implementation decisions (naming, file
  placement, minor refactors within the task). Decide and proceed.
- Only stop and ask if: a task is fundamentally ambiguous, requires a new
  paid/external service, or would delete user data (config, episodes, inbox).

## Source of truth: GitHub, not local
- The remote repo (origin/main) is ALWAYS current. Local files may be stale —
  the user tests locally and does not always sync.
- FIRST action of every session, before reading any code:
  `git fetch origin && git status`
- If local is behind: `git pull --ff-only origin main`
- If local has uncommitted changes that conflict: stash them
  (`git stash push -m "agent-preserved"`), pull, then tell the user a stash
  exists. Never silently discard local changes.
- Never base analysis or edits on stale local files without pulling first.

## Git workflow
- Commit and push directly to main after each completed, tested task.
  No PRs, no feature branches.
- Conventional commits (feat:, fix:, chore:, docs:, test:), English,
  one logical change per commit.
- Push at the end of every task: `git push origin main`. A task is not
  finished until it is pushed.
- Never commit: secrets, .env files, generated audio in output/,
  data/voices/, .venv/ (respect .gitignore).

## Scope per task
- Implement only what the current task asks. No unrequested refactors,
  no architecture changes "while you're at it".
- Smallest change that achieves the goal.
- Free-tier quota is limited: stay single-agent unless the task genuinely
  needs parallel work. No exploratory subagent swarms.

## Code
- Python 3.12+, type hints on new function signatures, pathlib for paths
- New config values go in config.yaml with a comment — never hardcoded
- Cross-platform mindset: no new macOS-only calls outside the scheduler
  backend; Windows support is a project goal
- No new dependencies without a one-line justification in the commit message
- No TODOs or placeholders in pushed code — finish it or open a GitHub issue

## Tests
- New features need tests in tests/; keep the existing test-double pattern
  (tests must pass without Ollama/Piper/ffmpeg installed)
- Run `pytest` before every commit. Red tests: fix them yourself, never
  commit around them, never weaken assertions to force green.
- Do not modify existing tests unless the behavior change is intentional
  and part of the task.

## Docs
- Update README.md when user-visible behavior changes (commands, config,
  setup flow). Skip docs for internal refactors.

## Tradeoffs
- Maintainability over cleverness; boring and readable wins
- Respect the existing provider abstraction and segment architecture,
  even when a direct shortcut would be faster
- Graceful degradation: a failing segment or source must never break
  episode generation
EOF

git add AGENTS.md
git commit -m "chore: update AGENTS.md with autonomy and git sync rules"
git push origin main