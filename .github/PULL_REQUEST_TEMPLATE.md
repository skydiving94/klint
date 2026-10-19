## Summary
**GitHub Issue:** Fixes #<number>

## Root Cause (for bugs)
<What caused the defect, and why it was not caught earlier.>

## Change List
- <Change, with the module or file it touches>

## Out of Scope
- <Related work deliberately not done here>

## Review Notes
- Start with: <file or commit that explains the rest>
- Needs close attention: <tricky logic, trade-offs>
- Safe to skim: <generated code, renames, formatting>

## Test Plan

### Instructions
<Setup needed to run the tests, if not trivial.>

### <Topic 1>
- [ ] Verify that <observable outcome>

### Regression
- [ ] Verify that <existing behavior> is unchanged

## Verification Checklist
- [ ] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy` and `uv run lint-imports` pass
- [ ] Tested locally against `klint examples/` and `klint-project examples/mock_bad_project/`
- [ ] If adding or updating rules: phrased as a positive practice (`"<positive practice> rather than <antipattern>?"`) and verified confidence scores on both passing and failing examples

## Risk and Rollback
- Risk: <what could break, and who would notice>
- Rollback: <revert the PR / disable a flag / migration steps>