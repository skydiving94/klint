# Code-unit accuracy set

Python modules whose every file, class and function follows klint's code
rules, and problems planted in them one at a time. It scores a judge on
`klint`'s checks of file, class and function units, by the unit's length,
to choose the character budget each judge gets.

## Running it

From the repository's root, with the judge chosen as for klint's commands:

```bash
KLINT_JUDGE_MODE=remote uv run python -m judge_accuracy.code_units
```

Against Jev, through GitHub and the repository's secret:

```bash
gh workflow run klint.yml --repo skydiving94/klint --ref <branch> -f command=judge-accuracy -f target=judge_accuracy/code_units -f min_confidence=0.0
```

The report is Markdown on stdout, ready to post. Progress and refusals go
to stderr. `--min-confidence` sets the threshold the tables use; the
budget is given at several thresholds.

## A case module

Two files of the same name:

- `<name>.py`, the true module: a backend module of a shop, with its
  database, payment provider and other services behind interfaces it is
  given.
- `<name>.json`, its planted problems:

```json
{
  "schema_version": 1,
  "about": "What the module does, and anything worth knowing about it.",
  "planted_problems": [
    {
      "rule_id": "n_plus_1_query",
      "old_text": "Text that occurs exactly once in the true module.",
      "new_text": "The text put in its place, which breaks the rule.",
      "why_wrong": "How the new text breaks the rule."
    }
  ]
}
```

## What is judged

- Every unit is shown to the judge whole: the command sets the budget of
  file, class and function units past any unit's length.
- Each module is judged whole, and cut to prefixes so that every band of
  length has units. A prefix ends after a top-level statement, or after a
  statement in the body of a top-level function, which it then ends with.
  For each band, the command judges the longest prefix whose file is in it,
  and for each top-level function the longest prefix that cuts that
  function to it.
- Every unit of every prefix is a true case.
- Each planted problem is planted in each prefix that holds its whole
  `old_text`. A unit of the true prefix that it changes is a planted case
  when the unit is asked the rule the problem breaks. A unit the problem
  adds, such as a method planted in a class, is not a case: the problem
  lies in the unit it was added to.
- A unit judged twice with the same text counts once.
- The module is written to an `api/` folder before it is judged, so that
  its file is tagged as backend code and every backend rule is asked.

## Labelling rules

- A true module follows every rule asked of its units:
  - queries are parameterized, name their columns and are batched;
  - secrets come from the environment;
  - errors reaching a caller say nothing of internals;
  - async code never blocks on I/O;
  - outside input is checked before use;
  - outside services sit behind an interface the module is given;
  - each file, class and function does one job. A long function is long
    because its one job has many parts, such as checking every field of a
    record or writing every section of one report; the steps of a flow,
    such as checking, pricing, paying and storing an order, are functions
    of their own, called by a short one.
- A planted problem breaks one rule, at one place, and leaves the rest of
  the module true. It does not add the imports its new code would need: no
  unit shows a module's imports and the code it changes together.
- Problems are planted at the start, the middle and the end of long
  functions and modules, so that a long unit's problem is not always near
  its first line.
- Fake secrets use no real provider's key format, so that secret scanning
  does not stop a push.

## Scoring

- **Caught**: a check failed on the planted unit, at or above the
  threshold. **Caught by its own check**: the rule the problem breaks failed.
- **Wrongly flagged**: a check failed on a true unit.
- A unit the judge refused to answer about is a refusal, never a miss.
- **The margin**: a band of length meets it when it catches at least 95% of
  the catch rate below 2,000 characters, and wrongly flags at most 2 points
  more of its true units than below 2,000.
- **The budget** at a threshold is the upper length of the last band, going
  up from 2,000, before the first band that does not meet the margin; 2,000
  when the first one does not. A band with no planted or no true unit stops
  it too.

## Limits

- A Python file unit is asked only `hardcoded_secrets` and `tight_coupling`;
  the Python pack asks the other rules of functions and classes. Long units
  are mostly files, short ones mostly functions, so the report also breaks
  the scores down by kind of unit.
- The bands are scored from a few hundred units, so a band's rates move by
  several points when one unit changes.
