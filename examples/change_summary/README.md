# Change-summary example

Two change-summary documents for one real change in this repository,
commit `d35fa76` ("Listing a binary file by name only in the project audit").

- The hunk code is the output of `git diff -U0 d35fa76^ d35fa76`, copied
  line for line: 4 files, 10 hunks.
- The summaries were written the way an agent would write them. Levels:
  hunk, file, package (`src/catalog/code/common`, `tests`), and the root
  package `.`, whose summary is the commit's.

| File | What it holds |
| --- | --- |
| `summaries.json` | Every summary is true of the level below it. |
| `summaries_with_planted_errors.json` | The same document with two summaries changed, at different levels. |

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

Start the judge as the repository's `CLAUDE.md` describes, then:

```bash
KEV_MODE=remote uv run klint-change-summary examples/change_summary/summaries.json
KEV_MODE=remote uv run klint-change-summary examples/change_summary/summaries_with_planted_errors.json
```

The summaries are judged children first: the hunks, then the files, the
packages, and last the commit. Above the hunks, the judge reads the summaries
one level down and what their own checks found, never the code.

Expected, with `jaredpalmer/kev-4b`:

- `summaries.json`: exit 0, "Every summary passed its checks."
- `summaries_with_planted_errors.json`: exit 1. Only the two planted
  summaries have problems of their own (`OWN PROBLEM`). Their ancestors,
  the delegator file, the package `src/catalog/code/common` and the commit,
  show `DESCENDANT PROBLEM`. On each unit, accuracy findings are listed
  before completeness findings.
