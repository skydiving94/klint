How to write the change summaries

Write the summaries of the uncommitted change to `.klint/change-summary.json`, as JSON in this form:

{
  "schema_version": 1,
  "git_change": {},
  "summary": "What the whole change does.",
  "packages": [
    {"path": "app", "summary": "What the change does in app/."}
  ],
  "files": [
    {
      "path": "app/greet.py",
      "summary": "What the change does to this file.",
      "hunks": [
        {"header": "@@ -5 +4,2 @@", "summary": "What this hunk's code does."}
      ]
    }
  ]
}

- `"git_change": {}` names the uncommitted change against HEAD: staged and unstaged edits, and untracked files that are not ignored. Keep it as it is.
- `files`: each changed file, by its path after the change, with its summary and an entry for each of its hunks.
- `hunks`: each hunk is named by its header as `git diff -U0 HEAD` writes it; for an untracked file, as `git diff -U0 --no-index /dev/null <path>` writes it. Text after the closing `@@` may be left out. A binary file, or a file renamed without edits, has no hunk: give it a file summary only.
- `packages`: optional. Directories whose changed files you sum up together. Each file and package belongs to the deepest listed package that holds it, else directly to the commit.
- `summary`: the whole change, summed up from what belongs directly to the commit.

What klint checks, one level at a time:
- A hunk's summary against the hunk's code.
- A file's summary against the summaries of its hunks; a package's against the summaries of the files and packages directly in it; the commit's against the summaries directly in it.
- In each check, your summary is the "hypothesis" and its evidence is the "premise".
- A summary may not state anything its evidence does not show, nor a reason, goal or benefit its evidence does not state. It may not contradict a summary one level down. It must mention every change its evidence shows.

So describe what the code does, not why, unless the code or a summary one level down says why. Sum up the level below without adding to it.
