# Change-summary accuracy set

Labelled change summaries of real commits of this repository, for scoring a
judge on `klint-change-summary`'s checks. One case file per commit.

## Running it

From the repository's root, with the judge chosen as for klint's commands:

```bash
KLINT_JUDGE_MODE=remote uv run python -m judge_accuracy.change_summary
```

The report is Markdown on stdout, ready to post. Progress and refusals go
to stderr. `--min-confidence` sets the threshold the main tables use; the
report also lists the results at several thresholds.

## A case file

```json
{
  "schema_version": 1,
  "about": "Which commit, and anything worth knowing about it.",
  "true_document": { "...": "a change-summary document; every summary in it is true" },
  "planted_mistakes": [
    {
      "summary_pointer": "#/files/0/hunks/2/summary",
      "mistake_kind": "false_statement",
      "summary": "The wrong summary put in its place.",
      "why_wrong": "What is wrong with it."
    }
  ]
}
```

- `true_document` is read as `klint-change-summary` reads a document, in
  either form: with the code of each hunk, or summaries only, naming the
  commit in `git_change`.
- Every summary in `true_document` is a true case. Each planted mistake is a
  case of its own: the true document with one summary replaced, judged on
  its own.
- `summary_pointer` is where the replaced summary sits, as a finding's
  location gives it.
- `mistake_kind` is one of `false_statement`, `unsupported_reason`,
  `contradiction` (file, package and commit summaries only) and `omission`.

## Labelling rules

- A true summary is true of the level below it, gives no reason the level
  below does not state, and mentions every change the level below shows.
- A planted summary makes one mistake of its kind and is otherwise the true
  summary.
- A hunk summary says only what the hunk's lines show. The judge never sees
  the lines around a hunk, so it cannot see the class or function the hunk
  sits in.

## Scoring

- **Caught**: a check failed on the planted summary, at or above the
  threshold. **Caught by its own check**: the check written for that kind
  failed.
- **Wrongly flagged**: a check failed on a true summary.
- **"Cannot tell" answers**: the share of the answers that were "Cannot Tell".
- A summary the judge refused to answer about is a refusal, never a miss.
- Hunks whose code does not fit within the judge's character budget are
  scored apart from the others, under "code over the cut".
