# Contributing to klint

Thank you for contributing to `klint`! Contributions of all kinds—new language extractors, unit types, rule pack refinements, performance improvements, and CI/MCP integrations—are welcome.

## Set Up

`klint` uses [uv](https://docs.astral.sh/uv/). Clone the repository (or your fork), then:
~~~bash
uv sync
uv run pre-commit install
~~~
`uv sync` installs `klint`, the development tools and the local judge, `kev`, which runs on Python 3.12 or 3.13. The pre-commit hook runs ruff, ruff format and mypy on each commit.

## Checks

Each of these passes before a pull request is opened:
~~~bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run lint-imports
~~~

The tests never load a model: they use the fake judge in `tests/support/fakes.py`.

## Running the Commands Against a Judge

Start a `kev.serve` server and leave it running:
~~~bash
uv run python -m kev.serve --run jaredpalmer/kev-4b --port 8009
~~~
Then, in another shell, run each command on its examples:
~~~bash
KLINT_JUDGE_MODE=remote uv run klint examples/
KLINT_JUDGE_MODE=remote uv run klint-structure examples/mock_bad_project/
KLINT_JUDGE_MODE=remote uv run klint-change-summary examples/change_summary/summaries.json
~~~
The first two find the planted problems and exit with 1; the third finds none and exits with 0. [examples/change_summary/README.md](../examples/change_summary/README.md) describes what the change-summary examples should give.

To ask Jev instead, see "Using Jev" in the [README](../README.md#using-jev-typesafes-hosted-api).

## Layout

~~~text
klint/
├── cli/                     # The console scripts, their options, exit codes and terminal report
├── app/                     # What runs an audit: settings (environment, klint.json), the injector, the kinds of audit on offer
│   └── pipeline/            # One audit run, in stages: acquisition, rule selection, auditing, roll-up
├── catalog/                 # The built-in suites
│   ├── domain_neutral/      # What fits any content: whole files, JSON documents, a change read from git, file traits (extension, tags, a project's overrides)
│   │   ├── extraction/
│   │   ├── file_traits_identifiers/
│   │   └── git/             # A commit, or the uncommitted change, read hunk by hunk
│   ├── code/                # The code suite: file contents (klint) and project structure (klint-structure)
│   │   ├── language_neutral/  # Units, renderers and extractors shared by every programming language
│   │   │   └── extraction/
│   │   └── python/          # Python file outlines, package units, and the class and function units of a file
│   └── change_summary/      # The change-summary suite (klint-change-summary)
│       ├── units/           # One unit for each hunk, file and package summary
│       └── renderers/       # What the judge reads about each summary
├── infra/                   # What the core is wired to
│   ├── rule_loader/         # JSON rule packs, checked against the registered unit types
│   ├── table_loader/        # JSON tables: each language's file extensions, and tag detection
│   └── system_one/          # Judges in the System One format: over HTTP (remote) or in this process (local)
├── core/                    # The auditor, the registry of unit types and klint's warnings
│   ├── interfaces/          # What the outer layers implement: extractors, renderers, judges, rule loaders, suites
│   └── models/              # The data the layers pass to one another
│       ├── audits/  judging/  reports/  rules/  scanning/  units/
└── resources/catalog/       # Built-in rule packs and tables, laid out like catalog/
    ├── code/language_neutral/   # backend.json, file_design.json, language_to_file_extensions.json, tag_detection.json
    ├── code/python/             # package_structure.json, functions_and_classes.json
    ├── code/typescript/         # react.json
    └── change_summary/          # summary_checks.json
tests/                       # Mirrors klint/; tests/support holds the fake judge, builders and a stub System One server
examples/                    # Deliberately bad code, a mock project and change-summary documents to run the commands on
~~~

`uv run lint-imports` checks the boundaries between packages:
* **Layers**: `cli` > `app` > `catalog` > `infra` > `core`. A layer imports only from the layers below it.
* **Core**: `klint.core` imports the standard library only.
* **Suites**: `app` and `core` import no named suite (`catalog.code`, `catalog.change_summary`); the caller chooses the suites an audit draws on. `catalog.domain_neutral` imports no named suite, and the named suites do not import one another: what two suites share belongs in `catalog.domain_neutral`.
* **Languages**: `catalog.code.language_neutral` does not import `catalog.code.python`.

## Code Style

* Type every parameter and return; mypy runs in strict mode, and `klint/` may not use `Any`.
* A fixed set of options is an enum, never a string literal. Function names start with a verb. Files stay under 300 lines.
* Tests check results through public entry points (the commands, an extractor's `extract`, the auditor), not internal mechanisms.

## Common Changes

### Adding or refining a rule
* Edit the pack in `klint/resources/catalog/`. A pack's `"applies_to": {"languages": [...]}` header limits it to files of those languages; a pack without one is asked about files of every identified language.
* Always phrase the `"question"` as a positive practice, `"<positive practice> rather than <antipattern>?"`, and give its `"unit_types"`. The README's "Writing a rule" lists every field.
* A new pack is listed in `_BUILT_IN_RULE_PACKS` in `klint/app/settings.py`.

### Adding a language to `klint-structure`
1. List the language's file extensions in `klint/resources/catalog/code/language_neutral/language_to_file_extensions.json`.
2. In `klint/catalog/code/<language>/`, subclass `BaseFileMetadataExtractor` to outline a file, and `BaseDirectoryUnitFactory` if the language has packages of its own.
3. Bind them under the language's name in `CodeSuiteModule.configure` (`klint/catalog/code/code_suite.py`). A language with nothing bound is handled by the language-neutral fallbacks.
4. Add the new package to the "language-neutral code does not import one language" contract in `pyproject.toml`.

### Adding a suite
1. Create `klint/catalog/<suite>/` with its unit classes (subclasses of `AuditableUnit`, each with a `unit_type`), an extractor (`BaseUnitExtractor`), a renderer for each unit class (`BaseUnitRenderer`, whose `find_known_answers` may answer a rule without the judge), and a `BaseSuite` whose `list_audit_kinds()` returns its `AuditKind`s and whose `register_unit_types()` registers its units.
2. Add an injector `Module` that multibinds the suite to `list[BaseSuite]`, and install it in `BuiltInSuitesModule` (`klint/catalog/built_in_suites.py`).
3. Add the suite to the suite contracts in `pyproject.toml`.
4. For a command of its own, add an `AuditCommand` in `klint/cli/` and a console script in `pyproject.toml`.

`klint/catalog/change_summary/` is a complete example.

## Pull Requests

1. Create a branch, commit, push it, and open a pull request against `main`.
2. Make sure the checks above pass.
3. **Self-Audit**: on each pull request into `main` and each push to `main`, the "klint Self-Audit" workflow runs `klint-structure` (minimum confidence 0.50) and `klint` (0.75) on `klint/`, asking Jev with the repository's `KLINT_JUDGE_API_KEY` secret. It lists the findings in the job summary. It reports and does not block: it fails only when an audit cannot run. A run without the secret, such as one for a pull request from a fork, skips the audits and says so. A maintainer can also run it on a branch of this repository from the Actions tab ("Run workflow").
4. **Merge rule**: before a pull request into `main` merges, each self-audit finding is fixed. A finding that is not valid is rebutted instead, in a comment on the pull request that says why.

To reproduce the Self-Audit locally, export your `KLINT_JUDGE_API_KEY` as the README's "Using Jev" shows, then:
~~~bash
export KLINT_JUDGE_MODE=remote KLINT_JUDGE_BASE_URL=https://api.typesafe.ai KLINT_JUDGE_MODEL=jev-latest
uv run klint-structure klint/ --min-confidence 0.50
uv run klint klint/ --min-confidence 0.75
~~~
