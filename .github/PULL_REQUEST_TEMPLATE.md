## Summary
<!-- Briefly describe what this PR adds, fixes, or improves -->
### Cause (if applicable)

### Change List

## Scope of Change
- [ ] **Core / Engine / CLI** (`src/core/`, `src/cli/`, `src/config/`)
- [ ] **Extractor / AuditableUnit Extension** (`src/infrastructure/extractors/`, `src/core/domain/units/`)
- [ ] **Evaluator / Integration** (`src/infrastructure/kev/`, CI, MCP, hooks)
- [ ] **Rule Pack Update** (`resources/default_rules.json`, `resources/default_project_rules.json`)
- [ ] **Documentation / Examples / Tests**

## Test Plan
<!-- Briefly describe how code reviewer can verify your code changes. -->

## Verification Checklist
- [ ] Preserves hexagonal boundaries (`src/core/` remains free of external I/O or ML framework imports)
- [ ] Tested locally against `klint examples/` and `klint-project examples/mock_bad_project/`
- [ ] If adding or updating rules: phrased as a positive practice (`"<positive practice> rather than <antipattern>?"`) and verified confidence scores on both passing and failing examples
