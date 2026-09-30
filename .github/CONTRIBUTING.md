# Contributing to klint

Thank you for contributing to `klint`! Contributions of all kinds—new language AST extractors, auditable unit types, rule pack refinements, performance improvements, and CI/MCP integrations—are welcome.

## Pull Request Workflow

1. **Fork & Clone**: Click **Fork** at the top-right of this repository, then clone your fork locally:
   ~~~bash
   git clone <your-fork-url>
   cd klint
   pip install -e .
   ~~~
2. **Create a Feature Branch**:
   ~~~bash
   git checkout -b feat/your-feature-name
   ~~~
3. **Follow Hexagonal Boundaries (`src/`)**:
   * Keep `src/core/` (`domain/`, `interfaces/`, `services/`) pure and free of external I/O or ML framework imports.
   * Place concrete extractors, model evaluators, and rule loaders under `src/infrastructure/`.
   * When adding or refining rules in `resources/`, always phrase `"instructions"` as a positive practice: `"<positive practice> rather than <antipattern>?"`.
4. **Verify Locally Before Opening a PR**:
   ~~~bash
   # Test file-level auditing across Python & React/TypeScript examples
   klint examples/

   # Test recursive project-structure auditing & cycle detection
   klint-project examples/mock_bad_project/
   ~~~
5. **Open a Pull Request**: Push your branch to your fork and open a Pull Request against `main`.

For a full breakdown of the repository structure and custom `AuditableUnit` / `BaseUnitExtractor` code examples, see the **[Contributing: Getting Started Guide](../README.md#contributing-getting-started-guide)** in the main README.