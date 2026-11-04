# Change-summary example

Change-summary documents for one real change in this repository,
commit `d35fa76` ("Listing a binary file by name only in the project audit").

- The summaries were written the way an agent would write them. Levels:
  hunk, file, package (`src/catalog/code/common`, `tests`), and the root
  package `.`, whose summary is the commit's.
- Each document comes in two forms that hold the same summaries:
  - **With the code.** The hunk code is the output of
    `git diff -U0 d35fa76^ d35fa76`, copied line for line: 4 files, 10 hunks.
  - **Summaries only.** The document names the commit in `git_change`, and
    klint reads its hunks from git. A hunk is named by its header, as
    `git diff -U0` writes it, such as `@@ -20,0 +21 @@`.

| File | What it holds |
| --- | --- |
| `summaries.json` | Every summary is true of the level below it, with the code. |
| `summaries_with_planted_errors.json` | The same document with two summaries changed, at different levels. |
| `summaries_only.json` | The summaries of `summaries.json`, without the code. |
| `summaries_only_with_planted_errors.json` | The summaries of `summaries_with_planted_errors.json`, without the code. |

## The planted errors

1. **A false statement, at the hunk level.** Hunk
   `src/catalog/code/common/extractors/traits_based_extraction_delegator.py#3`
   says the delegator "raises a ValueError when the file is likely binary".
   The code returns a metadata unit for such a file; it raises nothing.
2. **An unsupported reason, at the package level.** Package `tests` adds
   "They were added because the previous release ran out of memory on
   projects with large images." Nothing in the change mentions memory or
   images.

## Running it

Start the judge as the repository's `CLAUDE.md` describes, then, from the
repository's top directory:

```bash
KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries.json
KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries_with_planted_errors.json
KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries_only.json
KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries_only_with_planted_errors.json
```

A summaries-only document is checked against the git repository of the
current directory, so the commit must be in your clone (a shallow clone may
lack it).

The summaries are judged children first: the hunks, then the files, the
packages, and last the commit. Above the hunks, the judge reads the summaries
one level down and what their own checks found, never the code. Both forms
of a document give the judge the same texts.

Expected, with `jaredpalmer/kev-4b`:

- `summaries.json` and `summaries_only.json`: exit 0, "Every summary passed
  its checks."
- `summaries_with_planted_errors.json` and
  `summaries_only_with_planted_errors.json`: exit 1. Only the two planted
  summaries have problems of their own (`OWN PROBLEM`). Their ancestors,
  the delegator file, the package `src/catalog/code/common` and the commit,
  show `DESCENDANT PROBLEM`. On each unit, accuracy findings are listed
  before completeness findings.
