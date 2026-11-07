# klint: instructions for engineering sessions

## Source of truth
- Epic #67, "Agent-Ready Checks": goal, issue order and dependencies, decisions needed from the director, done-when.
- Your assigned sub-issue: its decisions and names are settled. Do not reopen them.
- `README.md` and `.github/CONTRIBUTING.md` are out of date until #62 rewrites them. Do not follow their layout notes or setting names. Edit them only where your issue asks; #70 updates the summary sections (features, limitations, roadmap) once the rest of the epic has merged.

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
  `git fetch origin && git worktree add ~/Developer/klint-cc/klint-issue-62 -b issue-62 origin/issue-62`
- Every local folder made for klint work goes under `~/Developer/klint-cc/`: worktrees, trial projects, scratch repositories. Create it if it is missing.
- Before merging, rebase onto `epic-67` if it has moved.
- Never two sessions in one working copy.
- A stale `.git/index.lock`: remove it only after checking that no git process is running.

## Working loop
1. Read #67, your issue, and its last handoff comment.
2. Work in small verified steps. One commit per step, then push.
3. Open a draft PR from the first commit. Title `Issue #N - <title>`, base `epic-67`.
4. Report each step: summary of changes, verification, and the commit message.
5. Commit messages start with the continuous form of the verb: "Adding", "Updating", "Removing".
6. Before marking the PR ready, run Self-Audit on your branch (below), and fix or rebut each finding.
7. At every stop, comment on the issue: done, next, blockers.

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
- Hosted Jev needs `KLINT_JUDGE_API_KEY`. It lives only in the repository secret and the director's own shell. Never ask for the key, and never write it to a file.
- To ask Jev yourself, have GitHub run one command on your pushed branch with the secret:
  `gh workflow run klint.yml --repo skydiving94/klint --ref issue-N -f command=klint-change-summary -f target=examples/change_summary/summaries.json -f min_confidence=0.8`
  - `command` is one of `klint`, `klint-structure`, `klint-change-summary` and `judge-accuracy`. `target` is a path in the repository; leave it empty for the command's example, or for `judge-accuracy`'s built-in set.
  - Find the run and read its report as for Self-Audit (below): `gh run list`, `gh run watch`, `gh run view --log`. The report is also in the job summary.
  - Exit 1 (problems found) leaves the run green; it fails only when the command cannot run.

## Self-Audit
Run it on your issue branch before marking a PR ready, and on `epic-67` before it goes to `main`. GitHub runs it: it audits `klint/` on that branch with Jev, using the repository secret, so the key never reaches your session.
1. Start it, then find the run and wait for it:
   `gh workflow run klint.yml --repo skydiving94/klint --ref issue-N`
   `gh run list --repo skydiving94/klint --workflow klint.yml --branch issue-N --limit 1`
   `gh run watch <run-id> --repo skydiving94/klint`
2. Read the findings of both audits, structure and file, in the log: `gh run view <run-id> --repo skydiving94/klint --log`.
3. Check each finding against the code; the judge has false positives, so never change code only because it was flagged. Fix each valid finding. Rebut each one that is not valid in a comment on the PR, naming the rule, the package and the facts. A finding already rebutted on an earlier PR may cite that rebuttal. Then exclude it in the repository's `klint.json` under `rule_exclusions`: its `rule_id`, the `paths` it doesn't apply to, and the comment's link as the `reason`. Remove an exclusion once its finding is fixed.
4. Record the run, and the link to the rebuttal comment, in the PR.
- Both audits run at `--min-confidence 0.8`. The run fails when an audit cannot run, or when it finds a problem that is neither fixed nor excluded; each audit's report lists the exclusions it applied.
- The self-audit triage at each epic's start and end (`klint-structure klint/` against Jev) uses `--min-confidence 0.50`. A finding below it needs no rebuttal; one from 0.50 to 0.8 is rebutted in a comment but needs no exclusion, since Self-Audit does not report it.
- A branch cut from `epic-67` before e1cb0a6 cannot be started by hand: rebase it onto `epic-67` first.
