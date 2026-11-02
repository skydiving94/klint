# klint: instructions for engineering sessions

## Source of truth
- Epic #67, "Agent-Ready Checks": goal, issue order and dependencies, decisions needed from the director, done-when.
- Your assigned sub-issue: its decisions and names are settled. Do not reopen them.
- `README.md` and `.github/CONTRIBUTING.md` are out of date until #62 rewrites them. Do not follow their layout notes or setting names. Edit them only where your issue asks.

## Project exceptions
These override personal defaults for work under #67.
- Run `git` and `gh` yourself: branch, worktree, commit, push, open PRs, comment on issues.
- Squash-merge issue → `epic-67` after internal review. Never merge into `main`; the director merges `epic-67` into `main`.
- Work through your assigned issue without waiting for a "start working" message.
- A name your issue does not settle: choose a self-explanatory one and list it in the PR description.
- Escalate to the director only for a decision #67 lists, or a question about the tool's overall behavior or between competing best practices. Decide the rest and record why in the PR.

## Branches
- `main` ← `epic-67` ← `issue-n`.
- Start an issue only after the issues it depends on (#67's table) have merged into `epic-67`.
- Create the branch from the issue, so it shows in the issue's Development section, then give it its own worktree:
  `gh issue develop 62 --name issue-62 --base epic-67`
  `git fetch origin && git worktree add ../klint-issue-62 -b issue-62 origin/issue-62`
- Before merging, rebase onto `epic-67` if it has moved.
- Never two sessions in one working copy.
- A stale `.git/index.lock`: remove it only after checking that no git process is running.

## Working loop
1. Read #67, your issue, and its last handoff comment.
2. Work in small verified steps. One commit per step, then push.
3. Open a draft PR from the first commit. Title `Issue #N - <title>`, base `epic-67`.
4. Report each step: summary of changes, verification, and the commit message.
5. Commit messages start with the continuous form of the verb: "Adding", "Updating", "Removing".
6. At every stop, comment on the issue: done, next, blockers.

## Code rules
- Type every parameter. Composed types (dicts, lists, tuples) become named classes; a pure lookup dict may stay, named `a_to_b`.
- A fixed set of options is an enum, never a string literal.
- Function names start with a verb. Files stay under 300 lines.
- Flag a poor existing design when you touch it, in the PR description.
- Tests check results through public entry points (commands, `extract`, the auditor), not mechanisms. Use the fake judge in `tests/support/fakes.py`.
- Code comments stay generic: no issue numbers, no notes on the current wiring.

## Commands
- Set up once: `uv sync && uv run pre-commit install`
- Checks: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run lint-imports`
- The package folder is `klint/`.

## Live judge
Run it before marking a PR ready if the change affects what the judge is asked or how its answers are read, and before `epic-67` goes to `main`.
1. Start the model server in the kev checkout (`uv sync --extra serve` once first):
   `cd ~/Developer/kev && uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009`
2. In the klint worktree, run against it (the default URL is already `http://127.0.0.1:8009`):
   `KLINT_JUDGE_MODE=remote uv run klint examples/`
   `KLINT_JUDGE_MODE=remote uv run klint-structure examples/mock_bad_project/`
   `KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries.json`
3. Record the results in the PR.
- One server can serve every session. If port 8009 is already serving, reuse it.
- Point at another server with `KLINT_JUDGE_BASE_URL`.
- Hosted Jev needs `KLINT_JUDGE_API_KEY`, which only the director sets in their own shell. Never ask for the key, and never write it to a file.
