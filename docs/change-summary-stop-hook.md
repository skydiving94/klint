# Checking an agent's change summaries with a Claude Code Stop hook

When Claude Code is about to stop, this hook has klint verify the agent's
summaries of its change. If a summary is flagged, the agent is sent back to
fix it. A retry cap makes sure a summary the judge keeps flagging cannot keep
the agent going forever. No MCP server is needed: the hook runs the
`klint-change-summary` command.

## How it works

1. The agent writes its summaries of the change to `.klint/change-summary.json`
   with the `summarize-commit-changes` skill. The code of each hunk comes from
   `git diff HEAD -U0` and the untracked files; the agent writes only the
   summaries.
2. When the agent stops, the hook runs `klint-change-summary --json` on that
   file. klint judges each hunk's summary against its code, then each file's,
   each package's and the commit's against the checked summaries one level
   down.
3. The hook lets the agent stop when every summary passes, or blocks the stop
   and tells the agent which summaries to fix.

| What the hook finds | What it does |
| --- | --- |
| No change in the working tree | Lets the agent stop. |
| No summaries file, or one older than a changed file | Blocks: asks for summaries of the current change. |
| klint exits 0: every summary passed | Lets the agent stop. |
| klint exits 1: some summaries are flagged | Blocks, listing each flagged summary and its checks. |
| klint exits 2 for a malformed summaries file | Blocks with klint's error. |
| klint exits 2 for another reason, such as the judge being down | Lets the agent stop, with a warning to you. |
| The hook has blocked 3 times in a row | Lets the agent stop, with a warning to you. |

The blocks in a row are counted per session in `.klint/stop-hook-attempts/`;
the count starts again once every summary passes or the hook gives up. The
Stop event's `stop_hook_active` flag is not enough for the cap: it only says
that the agent is already going on because of a Stop hook, which would allow
a single retry.

## Setting it up

1. Install klint so that `klint-change-summary` is on your `PATH`, or set
   `KLINT_CHANGE_SUMMARY_COMMAND` to the command to run, for example
   `uv run --project /path/to/klint klint-change-summary`.
2. Start the judge (see the "Live judge" section of klint's `CLAUDE.md`), and
   set `KEV_MODE=remote` in the environment Claude Code runs in.
3. Add `.klint/` to the project's `.gitignore`, so that the summaries file is
   not itself part of the change it summarizes.
4. Save the script below as `.claude/hooks/verify_change_summary.py`.
5. Add the hook to `.claude/settings.json`. Stop hooks take no matcher.
   Running klint takes a few seconds per summary, so the timeout is generous:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"${CLAUDE_PROJECT_DIR}/.claude/hooks/verify_change_summary.py\"",
            "timeout": 300
          }
        ]
      }
    ]
  }
}
```

## The hook script

```python
#!/usr/bin/env python3
"""Claude Code Stop hook: keep the agent working until klint passes its summaries.

Reads the Stop event on stdin. Prints a JSON decision on stdout and exits 0.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

# The most times the hook blocks a stop in one session before it gives up.
MAX_BLOCKS = 3
SUMMARIES = Path(".klint/change-summary.json")
ATTEMPTS_FOLDER = Path(".klint/stop-hook-attempts")
COMMAND = shlex.split(
    os.environ.get("KLINT_CHANGE_SUMMARY_COMMAND", "klint-change-summary")
)


def allow_stop(warning: str | None = None) -> None:
    if warning:
        print(json.dumps({"systemMessage": warning}))
    sys.exit(0)


def block_stop(reason: str, attempts_file: Path) -> None:
    attempts = int(attempts_file.read_text()) if attempts_file.exists() else 0
    if attempts >= MAX_BLOCKS:
        attempts_file.unlink()
        allow_stop(
            f"klint still flags the change summaries after {MAX_BLOCKS} tries; "
            f"stopping anyway. Last result:\n{reason}"
        )
    attempts_file.parent.mkdir(parents=True, exist_ok=True)
    attempts_file.write_text(str(attempts + 1))
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def list_changed_paths() -> list[Path]:
    """Return the changed and untracked paths that exist, .klint/ left out."""
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = [Path(line[3:].split(" -> ")[-1]) for line in status.splitlines()]
    return [
        path
        for path in paths
        if path.parts and path.parts[0] != ".klint" and path.exists()
    ]


def describe_flagged_summaries(klint_output: str) -> str:
    """Return one line per flagged summary: where it is and the checks it failed."""
    unit_id_to_rule_ids: dict[str, list[str]] = {}
    unit_id_to_context: dict[str, dict[str, str]] = {}
    for finding in json.loads(klint_output)["findings"]:
        unit_id_to_rule_ids.setdefault(finding["unit_id"], []).append(
            finding["rule_id"]
        )
        unit_id_to_context[finding["unit_id"]] = finding["context"]
    lines = [
        f"klint flagged these summaries in {SUMMARIES}. Rewrite each one so "
        "that it says only what its evidence shows: the hunk's code for a "
        "hunk, the summaries one level down for a file, a package or the "
        "commit. Then stop again."
    ]
    for unit_id, rule_ids in unit_id_to_rule_ids.items():
        context = unit_id_to_context[unit_id]
        lines.append(
            f"- {context['level']} {unit_id}: failed {', '.join(rule_ids)}. "
            f"Summary: {context['summary']}"
        )
    return "\n".join(lines)


def main() -> None:
    event = json.load(sys.stdin)
    os.chdir(os.environ.get("CLAUDE_PROJECT_DIR") or event["cwd"])
    attempts_file = ATTEMPTS_FOLDER / event["session_id"]
    changed_paths = list_changed_paths()
    if not changed_paths:
        allow_stop()
    if not SUMMARIES.exists() or SUMMARIES.stat().st_mtime < max(
        path.stat().st_mtime for path in changed_paths
    ):
        block_stop(
            f"Write the summaries of the current change to {SUMMARIES} with "
            "the summarize-commit-changes skill, then stop again.",
            attempts_file,
        )
    result = subprocess.run(
        [*COMMAND, str(SUMMARIES), "--json"], capture_output=True, text=True
    )
    if result.returncode == 0:
        attempts_file.unlink(missing_ok=True)
        allow_stop()
    if result.returncode == 1:
        block_stop(describe_flagged_summaries(result.stdout), attempts_file)
    # The last line says why the command stopped; any before it are skips.
    error_lines = result.stderr.strip().splitlines()
    error = error_lines[-1] if error_lines else f"exit status {result.returncode}"
    if "Change-summary document" in error or "is not valid JSON" in error:
        block_stop(f"Fix {SUMMARIES}: {error}", attempts_file)
    allow_stop(f"klint could not verify the change summaries: {error}")


if __name__ == "__main__":
    main()
```

## Trying it by hand

From the project directory, with a change in the working tree, feed the hook
a Stop event:

```bash
echo '{"session_id": "try-1", "cwd": "'"$PWD"'", "hook_event_name": "Stop", "stop_hook_active": false}' | python3 .claude/hooks/verify_change_summary.py
```

- With no summaries file, it prints a `"decision": "block"` asking for one.
- With summaries that klint flags, the `reason` lists each flagged summary.
  After 3 blocks in a row, whatever their reason, the next run prints a
  `systemMessage` instead and lets the agent stop.
- With summaries that all pass, it prints nothing and exits 0.

`examples/change_summary/` in klint holds a document with two planted
errors, and the same document without them.
