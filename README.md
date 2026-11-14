# klint
> **Semantic code auditing at the speed of Ruff, with the depth of an LLM—at zero token-generation cost.**

`klint` bridges the gap between rigid, syntax-bound linters (like ESLint or Ruff) and slow, expensive LLM code reviewers (like PR bots streaming tokens for 40 seconds). 
By leveraging the **System One (`/v1/systemone`)** pointer-head specification, `klint` evaluates files, package trees and an AI agent's summaries of its own change against custom JSON rule packs in a **single forward pass with zero decoded tokens**.

![klint CLI Output](docs/assets/cli-demo.png)

## Why klint?

* **Single-Pass, Zero-Generation Inference**: Evaluates an entire 16-rule pack in a single forward pass (~0.5s–2.5s per file locally on Apple Silicon MPS, or sub-second on CUDA / hosted `/v1/systemone`) rather than streaming hundreds of verbose reasoning tokens for 30+ seconds.
* **100% Local (`kev`) or Remote (`jev` / `kev.serve`)**: Run entirely offline on your machine using open-weight models (`kev-0.8b`, `kev-4b`) via Hugging Face, or point to any remote `/v1/systemone` endpoint (`jev` API or self-hosted `kev.serve`).
* **Declarative Plain-English Rules (`klint.json`)**: Define team-specific architectural rules or antipatterns using simple ESLint-style JSON configuration files—no complex AST or Semgrep DSL required.
* **Extensible by Suites**: Each suite brings its own unit types, extractors, renderers and rule packs, so teams can adapt `klint` to another language or another kind of audit without changing its core.

### How klint Compares (Related Work)

| Tool Category                      | Examples                                             | Speed & Cost                                     | Privacy                                  | Architectural & Semantic Depth                                                                                                                                                        |
| :--------------------------------- | :--------------------------------------------------- | :----------------------------------------------- | :--------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Deterministic Linters**          | ESLint, Ruff, Pylint, Semgrep                        | Instant, free                                    | 100% Local                               | **Syntax-bound**: Great for formatting and known AST patterns, but cannot judge domain cohesion, layering intent, or responsibility boundaries without brittle custom DSLs.           |
| **Generative LLM Reviewers**       | CodeRabbit, GPT/Claude PR Bots                       | Slow (20–45s/file), high token cost              | Cloud API (typically)                    | **High, but noisy**: Understands semantics, but relies on slow, non-deterministic autoregressive token generation.                                                                    |
| **Other System One (`jev`) Tools** | `ErisLint`, `jgrep`, `patdown`, `jev-pref`           | Fast (single forward pass)                       | Mostly Hosted `jev` API                  | **Flat file/diff scope**: Evaluates individual code chunks or diffs against rules, but lacks recursive package-tree modeling and native in-process `kev` execution.                   |
| **`klint`**                        | `klint`, `klint-structure`, `klint-change-summary`   | **Fast (single forward pass, 0 decoded tokens)** | **100% Local (`kev`) or Remote (`jev`)** | **File + Recursive Package Architecture**: Combines semantic code linting with composite Python AST directory trees, dependency rollups, and checks of an agent's change summaries.   |

## Features

* **File & Recursive Directory Auditing (`klint`)**: Scan individual source files or entire directory trees concurrently with live progress reporting and built-in concurrency throttling.
* **Recursive Python Project Structure Auditing (`klint-structure`)**: Audit Python package and directory hierarchies layer-by-layer, combining AST-based file metadata extraction (`imports`, `exports`, `classes`, `functions`, `line_count`, `__init__.py` public API status) with recursive subpackage dependency rollups and mutual cycle detection.
* **Change-Summary Checks (`klint-change-summary`)**: Check an AI agent's summary of its own change at every level: each hunk against its code, then each file, package and the commit against the checked summaries below it. False, unsupported or missing statements are flagged, false ones first.
* **[Python Classes & Functions as Units](#python-classes-and-functions)**: `klint` also judges each class and function of a Python file on its own, so a rule reads a short piece of code and a finding points to the exact method, with its lines.
* **[Change Summaries Read from Git](#change-summary-documents)**: An agent writes only its summaries, and `klint-change-summary` reads the change itself from git: a commit, or the uncommitted change.
* **[Claude Code Stop Hook](#claude-code-stop-hook)**: `klint-change-summary-stop-hook` keeps a Claude Code agent from stopping until its summaries of its change pass, and sends it back to fix the ones flagged.
* **[Local Kev or Hosted Jev](#judges)**: Run the judge on your machine, on a `kev.serve` server, or ask TypeSafe's hosted Jev with an API key. Each command's first line names the judge it asks.
* **[Project Layers for Structure Checks](#what-a-klintjson-holds)**: List a project's layers in `klint.json`, and `klint-structure` judges layering and leaking libraries against them. Its structure rules state their limits, such as the 15 modules a flat package may hold.
* **4-Way Semantic Judgment & Confidence Sorting**: Classifies rules into `Pass`, `Fail`, `Irrelevant`, or `Lack of Evidence`, automatically sorting findings from highest confidence to lowest and supporting `--min-confidence` filtering.
* **Built-In Backend, React & Architectural Rule Packs** (in `klint/resources/catalog/`):
  * **File rules**: `backend.json` (N+1 queries, hardcoded secrets, sync blocking I/O, missing input validation, tight coupling, and more, for back-end code in any language), `react.json` (prop drilling, improper state colocation, direct DOM manipulation, overusing `useEffect`, missing hook dependency arrays, for TypeScript and JavaScript) and `file_design.json` (god components).
  * **Structure rules (`package_structure.json`)**: Circular package dependencies, layering violations, god packages, junk-drawer modules, barrel-file sprawl, leaky abstractions, missing package public APIs, and business logic in presentation layers.
  * **Change-summary checks (`summary_checks.json`)**: Accuracy (no false statement, no unsupported reason, no contradiction with the level below), completeness, and a summary for every hunk, file and commit (`has_summary`, answered by `klint` itself).

## Installation & Quickstart

### Prerequisites
* Python 3.11 or later. The local judge, `kev`, runs on Python 3.12 or 3.13.

### Install
~~~bash
git clone https://github.com/skydiving94/klint.git
cd klint
pip install -e ".[local]"
~~~
The `local` extra installs `kev`, which runs the judge model on your machine. To ask only a remote judge (a `kev.serve` server or Jev), `pip install -e .` is enough.

### Quickstart
The default judge is `jaredpalmer/kev-4b`, run on your machine; the first run downloads it from Hugging Face.
~~~bash
# Audit a file or a directory against the file rules
klint examples/backend_data_and_security.py

# Audit a Python project's structure
klint-structure examples/mock_bad_project/

# Check an agent's summaries of a change
klint-change-summary examples/change_summary/summaries.json

# The same summaries alone, with the change read from git (commit d35fa76)
klint-change-summary examples/change_summary/summaries_only.json
~~~

## Commands

| Command | What it audits | Argument |
| :--- | :--- | :--- |
| `klint` | The contents of each file, and of each class and function in a Python file, against the file rules. | A file or a directory. |
| `klint-structure` | The structure of a project: each directory and Python package, from an outline of each file (imports, exports, classes, functions, line count). | A directory. |
| `klint-change-summary` | An agent's summaries of a change: each hunk against its code, and each file, package and the commit against the checked summaries below it. | A change-summary JSON document: summaries with each hunk's code, or summaries alone; see [Change-summary documents](#change-summary-documents). |
| `klint-change-summary-stop-hook` | Run by Claude Code before its agent stops: the agent's summaries of the uncommitted change, in `.klint/change-summary.json`; see [Claude Code Stop Hook](#claude-code-stop-hook). | None: it reads the Stop event on stdin. It takes only `--min-confidence`. |

The first three commands take these options:

| Option | What it does |
| :--- | :--- |
| `--rules PATH` | Adds the rules in a JSON file. They merge over the built-in rules; a rule with the same ID replaces the built-in one. |
| `--min-confidence N` | Reports only the failures with at least this confidence, from 0.0 to 1.0 (default 0.0). |
| `--all-answers` | Shows every answer, not only the problems. |
| `--json` | Prints JSON instead of the terminal report. |

For example:
~~~bash
klint examples/ --min-confidence 0.65
klint examples/ --all-answers
klint examples/ --json
klint-structure examples/mock_bad_project/ --min-confidence 0.25 --json
~~~

### Change-summary documents
`klint-change-summary` takes a JSON document in one of two forms. Both hold a summary for each hunk, each file, each package you choose to summarize, and the whole commit.

| Form | What it holds | Where the code comes from |
| :--- | :--- | :--- |
| With the code | `diff_command`, and a nested `root_package` whose hunks hold their removed and added lines. | The document. |
| Summaries only | `git_change`, the commit's `summary`, and flat `packages` and `files` lists. | git, in the repository of the current directory. |

A summaries-only document, abridged from [examples/change_summary/summaries_only.json](examples/change_summary/summaries_only.json):
~~~json
{
  "schema_version": 1,
  "git_change": {"commit": "d35fa76"},
  "summary": "Lists a binary file by name only in the project audit, and adds tests for it.",
  "packages": [
    {"path": "tests", "summary": "Adds two tests that a binary file is listed by name only."}
  ],
  "files": [
    {
      "path": "src/catalog/code/common/extractors/traits_based_extraction_delegator.py",
      "summary": "Lists a likely binary file by name only.",
      "hunks": [
        {"header": "@@ -20,0 +21 @@", "summary": "Imports is_likely_binary."}
      ]
    }
  ]
}
~~~
* **The change**: `git_change.commit` names a commit as git does (`HEAD`, a hash), which is checked against its first parent. With no `commit`, as in `"git_change": {}`, the change is the uncommitted one against `HEAD`: staged and unstaged edits and untracked files, not ignored ones. The document's own file is never part of the change.
* **The hunks**: each hunk is named by its header as `git diff -U0` writes it, for example in the output of `git diff -U0 HEAD` or `git show -U0 <commit>`. Text after the closing `@@` is ignored. An untracked file is one hunk, `@@ -0,0 +1,N @@`. A binary file, or a rename without edits, has no hunk: summarize it at the file level. A renamed file is listed by its new path. In the report, a hunk is `<path>#<n>`, numbered from 1 in its file.
* **The packages**: optional directories you summarize. Each file and package sits in the deepest listed package that holds it, else directly in the commit.
* **A missing summary**: a hunk or file of the change, a listed package or the commit with no summary fails `has_summary` (exit 1). `klint` answers that check itself, with no confidence (and no `location` for a summary the document does not list), and answers "Cannot Tell" for the summary just above it, since the judge would read an incomplete premise there.
* **A summary that does not fit the change** stops the command (exit 2): a hunk, file or package the change does not hold, or a header that is not a hunk header. So do an unknown commit, a directory outside any git repository, and an empty change.

See [examples/change_summary/README.md](examples/change_summary/README.md) for both forms of one real change.

### What a command prints
* **The judge**: a line on stderr, before the audit, names the judge the command asks, for example `[klint] Judge: jaredpalmer/kev-4b, run in this process (local)`.
* **The report**: findings are grouped by unit and sorted by confidence. Each unit with a problem is marked `OWN PROBLEM`, or `DESCENDANT PROBLEM` when the problem is in a unit nested inside it.
* **JSON**: with `--json`, stdout holds one object: the audited units (`examined_files`, `examined_directories` or `examined_summaries`), `unit_id_to_roll_up_status`, and `findings`. Each finding gives its `rule_id`, `unit_id`, `answer`, `confidence`, `question`, `tags`, `location` (`path`, `start_line`, `end_line`) and `context` (for a Python class or function, its `qualified_name`).

### Exit codes
| Code | Meaning |
| :--- | :--- |
| `0` | No failure was found at the confidence `--min-confidence` asks for. |
| `1` | At least one failure was found at that confidence. |
| `2` | The audit could not run: for example, the target or a rules file cannot be used, the judge cannot be reached for any unit, or an unexpected error occurred. |

~~~bash
klint examples/; echo "exit=$?"
klint no/such/path; echo "exit=$?"
~~~

## Configuration & Custom Rules (`klint.json`)

Like ESLint, `klint` works out of the box from any directory and discovers a **`klint.json`** (or **`.klintrc.json`**, or **`.klintrc`**) file: first in the target's directory (the file's directory when the target is a file), then in the working directory. You can also pass rules explicitly with `--rules ./custom_rules.json`; a `--rules` file holds rules only.

### Settings
Each setting is taken from the first of these that sets it: an environment variable, the `"env"` block of the project's `klint.json`, the built-in default.

| Setting | What it sets | Default |
| :--- | :--- | :--- |
| `KLINT_JUDGE_MODE` | `local` runs the model in the `klint` process; `remote` asks a `/v1/systemone` server. | `local` |
| `KLINT_JUDGE_MODEL` | The model: a Hugging Face repo ID or a local path when local; the server's model name when remote (for example `jev-latest`). | `jaredpalmer/kev-4b` |
| `KLINT_JUDGE_BASE_URL` | The server's address, when remote. | `http://127.0.0.1:8009` |
| `KLINT_JUDGE_API_KEY` | The API key the server asks for, when remote. Set it in your shell, never in `klint.json`. | none |
| `KLINT_REPLACE_FILE_RULES` | A rules file that replaces every built-in rule pack for `klint`. | none |
| `KLINT_REPLACE_PROJECT_RULES` | A rules file that replaces every built-in rule pack for `klint-structure`. | none |

A relative path set in `klint.json` is taken from the folder of the `klint.json`.

### What a `klint.json` holds
* `"env"`: settings, from the table above.
* `"rules"`: rules that merge over the built-in ones; a rule with the same ID replaces the built-in one. Rules may also sit at the top level of the file.
* `"fallback_rule_packs"`: the rule packs asked about a file whose language `klint` cannot identify, in place of the built-in `backend.json` and `file_design.json`.
* `"file_traits"`: corrections to the language or tags `klint` detects for some files, for example `[{"glob": "web/**", "tags": ["frontend"]}]`. The first entry whose glob matches a file decides.
* `"layers"`: the project's layers, outermost first, for example `["myapp.cli", "myapp.services", "myapp.core"]`. `klint-structure` shows them to the judge when it asks `layering_violation` and `leaky_abstraction`, and takes the last as the core. Without them, both rules ask about layers in general terms.
* `"rule_exclusions"`: rules the project turns off for some of its paths, for example `[{"rule_id": "god_component", "paths": ["legacy/**"], "reason": "Being replaced by the new module"}]`. Each entry holds exactly a `rule_id`, `paths`, globs matched from the folder of the `klint.json` (a class or function by its file's path), and a `reason`. The rule is not asked about a matching unit, and every other rule still is. The report lists each exclusion it applied, and `--json` adds them as `applied_rule_exclusions` when there are some.

~~~json
{
  "env": {
    "KLINT_JUDGE_MODE": "local",
    "KLINT_JUDGE_MODEL": "jaredpalmer/kev-4b"
  },
  "rules": {
    "no_raw_print_statements": {
      "type": "choice",
      "question": "Does the code use a structured logger rather than raw print() statements for application logging?",
      "unit_types": ["file"]
    },
    "domain_purity": {
      "type": "choice",
      "question": "Does the core domain package remain free of database ORM and HTTP framework imports rather than coupling domain entities to infrastructure?",
      "unit_types": ["project_directory"]
    }
  }
}
~~~

### Writing a rule
Because `klint` evaluates whether code **follows** a practice (`Pass`) or **violates** it (`Fail`), always phrase the `"question"` as a positive practice: **`"<positive practice> rather than <antipattern>?"`**.

| Field | What it holds |
| :--- | :--- |
| `type` | `"choice"`. |
| `question` | The question the judge answers about each unit. |
| `question_with_layers` | The question asked instead, when the project's `klint.json` lists its `layers`; `{layers}` marks where they go, joined by commas. |
| `unit_type_to_question` | The question asked instead about a unit of each type named, for example `{"file_summary": "..."}`. A type the rule is not asked about is warned about. |
| `unit_types` | The units the rule is asked about: `file`, and `class` and `function` in a Python file (`klint`); `project_directory` and `file_metadata`, a file's outline (`klint-structure`); `hunk_summary`, `file_summary` and `package_summary` (`klint-change-summary`). Default `["file"]`. |
| `languages` | Limits the rule to files of these languages, for example `["python"]`. |
| `unit_tags` | Limits the rule to files with one of these tags, `backend` or `frontend`. A file with no detected tag is asked every rule. |
| `excluded_unit_tags` | Keeps the rule from units with one of these tags. `klint-structure` tags a Python package `data` when its tree holds no module but `__init__.py`, as a folder of data files does; the built-in `dead_code_module` and `missing_package_public_api` are not asked about it. |
| `tags` | Labels for what the rule is about, such as `"security"`. |

### Python classes and functions
`klint` reads a Python file as a `file` unit and, nested in it, a unit for each class and function. A rule for them is then asked about a short piece of code instead of the whole file, and its findings point to the exact method.

| Unit type | What it is | What the judge reads |
| :--- | :--- | :--- |
| `class` | Each class at the top of a file, and each class defined in a class. | The class with each method's body replaced by `...`: its decorators, bases, docstring, class-level statements and method signatures stay. |
| `function` | Each function at the top of a file, and each method, async or not. A function defined inside a function, such as a decorator's wrapper, is part of the outer function. | The function's source, decorators included. |

* A class or function defined inside an `if`, `try`, `with` or loop statement counts as defined where that statement is.
* **IDs and lines**: a unit's ID is its file's path and its qualified name, as in `shop/cart.py::Cart.add`. When two units share a qualified name, as a property and its setter do, each ID ends with its first line, as in `shop/cart.py::Cart.total:14`. A finding gives the unit's lines in `location` and its qualified name in `context`.
* **Roll-up**: a method sits under its class and a class under its file. A problem in a method marks its class and its file `DESCENDANT PROBLEM`.
* **Long units**: a class or function over the 2,000-character budget is shown from its first line, as far as the budget goes, as a long file is.
* **Unparseable files**: a Python file that cannot be parsed is still judged whole, with a warning, and its classes and functions are not judged on their own.

For Python, the built-in rules about one function are asked about each class or function instead of the whole file (`python/functions_and_classes.json`):
* `function`: `n_plus_1_query`, `improper_error_handling`, `sync_blocking_io`, `missing_input_validation` and `over_fetching_data`.
* `class` and `function`: `god_component`.
* `hardcoded_secrets` and `tight_coupling` stay on the whole file, where a module's constants and imports are.

For every other language, the built-in rules are still asked about the whole file.

~~~json
{
  "short_functions": {
    "type": "choice",
    "question": "Is each function short enough to read at a glance rather than running through many unrelated steps?",
    "unit_types": ["function"]
  }
}
~~~

## Judges

### Local (the default)
`KLINT_JUDGE_MODE=local` loads the model into the `klint` process; it needs the `local` extra. For a faster start on each run, use `KLINT_JUDGE_MODEL=jaredpalmer/kev-0.8b`, or keep a `kev.serve` server running.

### A `kev.serve` server
Start a server with the `kev` that the `local` extra installed, and leave it running:
~~~bash
python -m kev.serve --run jaredpalmer/kev-4b --port 8009
~~~
Then, in another shell:
~~~bash
KLINT_JUDGE_MODE=remote klint examples/
~~~

### Using Jev (TypeSafe's Hosted API)
`klint` can ask TypeSafe's hosted Jev model instead of a local `kev`, with no GPU and nothing else to install. You need a TypeSafe API key; see [docs.typesafe.ai](https://docs.typesafe.ai).

Set the key in your shell, not in `klint.json`, which is usually committed:
~~~bash
read -rs KLINT_JUDGE_API_KEY && export KLINT_JUDGE_API_KEY
export KLINT_JUDGE_MODE=remote KLINT_JUDGE_BASE_URL=https://api.typesafe.ai KLINT_JUDGE_MODEL=jev-latest
klint examples/
~~~

* **What leaves your machine**: the code of each audited unit (for `klint-change-summary`, each summary and its code) and the rule questions are sent to TypeSafe. Use the local `kev` for code that must stay on your machine.
* **Which judge**: each command's first line names the judge it asks, for example `[klint] Judge: jev-latest at https://api.typesafe.ai (remote, API key set)`. `klint` reads `KLINT_JUDGE_API_KEY`, not the `TYPESAFE_API_KEY` that TypeSafe's SDK reads.
* **A refused key**: `klint` skips each unit with "did not accept the API key" (or "needs an API key, and none was given") and exits with code 2 when no unit could be audited.

### Choosing a judge and a threshold
The defaults stay as they are: the local `jaredpalmer/kev-4b`, and `--min-confidence 0.0`. For `klint-change-summary`, a test set of 126 labelled summaries from 5 commits of this repository (73 true, 53 with a planted mistake) gave:

| Judge | Mistakes caught (0.0) | Omissions caught (0.0) | True summaries flagged (0.0) | Caught / flagged at the recommended threshold |
| :--- | ---: | ---: | ---: | :--- |
| `jev-latest` (hosted) | 50/53 | 12/12 | 19/73 | 42 / 6 at `0.8` |
| `jaredpalmer/kev-9b` (local, about 22 GB) | 44/53 | 5/12 | 6/73 | 30 / 1 at `0.5` |
| `jaredpalmer/kev-4b` (local, the default) | 38/53 | 0/12 | 8/73 | 25 / 0 at `0.5` |

* **With an API key**: Jev at `--min-confidence 0.8`. It is the only judge here that reliably catches an omission. Its false flags all come from `covers_every_change` above the hunk level.
* **Without one, or for code that must stay on your machine**: the default Kev-4B at `--min-confidence 0.5`. It flags no true summary, but catches about half the mistakes and no omissions.
* The set is small and labelled by one person, so a difference of two or three cases is noise. To score a judge yourself, see [CONTRIBUTING.md](.github/CONTRIBUTING.md#scoring-a-judge).

## GitHub Action

The repository is also a GitHub Action that runs `klint` or `klint-structure` in a workflow:

~~~yaml
jobs:
  klint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Audit with klint
        uses: skydiving94/klint@main
        with:
          target: "mypackage/"
          mode: "file"                      # "file" (klint) or "structure" (klint-structure)
          min_confidence: "0.65"
          judge_mode: "remote"
          judge_model: "jev-latest"
          judge_base_url: "https://api.typesafe.ai"
          judge_api_key: ${{ secrets.KLINT_JUDGE_API_KEY }}
~~~

| Input | Default | What it does |
| :--- | :--- | :--- |
| `target` | `.` | The file or directory to audit. |
| `mode` | `file` | `file` runs `klint`; `structure` runs `klint-structure`. |
| `min_confidence` | `0.60` | The least confidence a failure needs to be reported and to count as a problem. |
| `rules` | none | A rules file whose rules merge over the built-in ones. |
| `judge_mode` | `local` | Sets `KLINT_JUDGE_MODE`. `local` runs `kev` on the runner's CPU. |
| `judge_model` | `jaredpalmer/kev-0.8b` | Sets `KLINT_JUDGE_MODEL`. |
| `judge_base_url` | `http://127.0.0.1:8009` | Sets `KLINT_JUDGE_BASE_URL`. |
| `judge_api_key` | none | Sets `KLINT_JUDGE_API_KEY`. Pass it from a secret. |
| `fail_on_problems` | `true` | `true` fails the step when `klint` finds problems (exit 1); `false` reports them and passes. A run that cannot audit (exit 2) fails the step either way. |

* **Output**: `exit_code`, the command's exit code.
* **Job summary**: each run adds its report to the job summary.
* **Settings**: the Action always sets the judge's mode, model and address, so a `klint.json` `"env"` block does not choose the judge in the Action.

## Claude Code Stop Hook

`klint-change-summary-stop-hook` keeps a Claude Code agent from stopping until `klint-change-summary` passes its summaries of its change: everything it changed in the session, committed or not. Each time the agent is about to stop, the hook checks the summaries in `.klint/change-summary.json`. When they are missing, it asks the agent to write them, with instructions and the list of changed files and hunks. A flagged summary sends the agent back to fix it.

### Setting it up
1. **Install klint** (see [Install](#install)) so that `klint-change-summary-stop-hook` is on the `PATH` Claude Code starts with. Otherwise, give the command's full path in step 3, such as `/path/to/klint/.venv/bin/klint-change-summary-stop-hook`.
2. **Choose the judge** for the project, as for any `klint` command (see [Judges](#judges)): in the environment Claude Code starts with, or in an `"env"` block of a `klint.json` at the project's root. For a `kev.serve` server on the default port:
   ~~~json
   {"env": {"KLINT_JUDGE_MODE": "remote"}}
   ~~~
   Keep a Jev API key in the shell's environment, not in `klint.json`.
3. **Turn the hook on** in the project's `.claude/settings.json`, for both events:
   ~~~json
   {
     "hooks": {
       "SessionStart": [
         {"hooks": [{"type": "command", "command": "klint-change-summary-stop-hook"}]}
       ],
       "Stop": [
         {"hooks": [{"type": "command", "command": "klint-change-summary-stop-hook", "timeout": 300}]}
       ]
     }
   }
   ~~~
   At `SessionStart`, the hook records the commit the session starts at; at each `Stop`, it checks everything changed since, the commits the agent made included. Without the `SessionStart` entry, it checks the uncommitted change alone. Checking takes a few seconds a summary, so a large change may need a longer `timeout`. To block only on failures with at least some confidence, add an option to the `Stop` command, such as `klint-change-summary-stop-hook --min-confidence 0.5`.
4. **Commit** `.claude/settings.json` and any `klint.json` you added, or they are part of the change the agent is asked to summarize.

### What the hook does
| When the agent is about to stop | The hook |
| :--- | :--- |
| Nothing changed since the session's start commit, or, without one, the working tree has no change | Lets it stop. |
| There is no `.klint/change-summary.json`, or it does not name exactly the change's files and hunks | Blocks: asks for summaries of the current change, listing the files and hunks to summarize. |
| Every summary passes | Lets it stop. |
| `klint` flags summaries | Blocks, listing each flagged summary and the checks it failed. |
| The summaries file cannot be read, such as a JSON error or a field of the wrong kind | Blocks with `klint`'s error. |
| `klint` cannot check the summaries for another reason, such as the judge being down | Lets it stop, with a warning to you. |
| The hook has blocked 3 times in a row in this session | Lets it stop, with a warning to you and what it said last. |
| The session's start commit is no longer in the branch's history, after a rebase, an amend or a branch switch | Checks the uncommitted change alone, with a warning to you. |

* **The change**: from the commit recorded at the session's start to the working tree, as for `"git_change": {"base": "<commit>"}`: the commits made since, staged and unstaged edits, and untracked files, not ignored ones. The hook's messages name the exact `git_change` to write. Without a recorded start commit, it is the uncommitted change against `HEAD`, as for `"git_change": {}`. Commits made before the session are never checked.
* **The hook's own files**: the summaries go in `.klint/`, which the hook marks ignored with a `.klint/.gitignore`, so they are never part of the change, nor committed. The start commit and the blocks in a row are kept per session in the repository's git directory, outside the working tree; two sessions in one project each keep their own.
* **Blocks in a row**: the count starts again whenever the agent may stop, and at a stop that does not follow a Stop hook's block, such as the first after your next prompt.
* **Trying it by hand**: from the project, feed the hook a SessionStart event, make and commit a change, then feed it a Stop event:
  ~~~bash
  echo '{"session_id": "try-1", "cwd": "'"$PWD"'", "hook_event_name": "SessionStart", "source": "startup"}' | klint-change-summary-stop-hook
  echo '{"session_id": "try-1", "cwd": "'"$PWD"'", "hook_event_name": "Stop", "stop_hook_active": false}' | klint-change-summary-stop-hook
  ~~~
  The Stop prints a `"decision": "block"` with its reason, a `systemMessage` warning, or nothing when the agent may stop; the SessionStart prints nothing. Both always exit 0.

## Renamed in This Release

These names changed. Each old name still works until the next release and prints a warning naming its replacement.

| Old name | New name |
| :--- | :--- |
| `klint-project` | `klint-structure` |
| `--all` | `--all-answers` |
| `KEV_MODE`, `KEV_MODEL_NAME`, `KEV_BASE_URL`, `KEV_API_KEY` | `KLINT_JUDGE_MODE`, `KLINT_JUDGE_MODEL`, `KLINT_JUDGE_BASE_URL`, `KLINT_JUDGE_API_KEY` |
| `KEV_DEFAULT_RULES_PATH`, `KEV_DEFAULT_PROJECT_RULES_PATH` | `KLINT_REPLACE_FILE_RULES`, `KLINT_REPLACE_PROJECT_RULES` |
| Rule fields `instructions`, `target_unit_types` | `question`, `unit_types` |
| Action inputs `kev_mode`, `kev_model_name`, `kev_base_url`, `kev_api_key` | `judge_mode`, `judge_model`, `judge_base_url`, `judge_api_key` |
| Action input `mode: "project"` | `mode: "structure"` |

The source moved from `src/` to the `klint/` package, with no alias for code that imports it.

## Extending klint

`klint` is built from suites: the code suite (`klint`, `klint-structure`), the change-summary suite (`klint-change-summary`), and a domain-neutral suite they share. A suite adds its unit types, the extractors that read them, the renderers that write what the judge reads, and its rule packs. See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the layout and for how to add a rule pack, a language or a suite.

## Current Limitations (v0.1) & Performance Tips

* **Python Is the Only Language Parsed**:
  * `klint` reads any text-based source file. It also splits a **Python (`.py`)** file into its classes and functions; a file in any other language is judged whole (the built-in packs ship with rules for back-end code and for **React/TypeScript**; other languages can be targeted via custom rules in `klint.json`).
  * `klint-structure` relies on Python's `ast` module to extract `imports`, `exports`, `classes`, and `functions`, so deep structural extraction supports **Python** files only (other files fall back to file names and line counts until multi-language extractors land).
* **Long Units**: Small System One models (`kev-0.8b`, `kev-4b`) are most accurate on compact text (`<512` tokens). A unit over the 2,000-character budget is shown only as far as the budget goes, so a large non-Python file, or a long Python function, can get lower confidence scores.
* **Change Summaries**:
  * A hunk over the 2,000-character budget is shown only in part. The local Kevs flag such hunks' summaries whether they are true or not, and no judge sees a mistake that sits past the cut.
  * Jev flags some true summaries of a file, package or commit on `covers_every_change`, reading "every change" as every detail. See [Choosing a judge and a threshold](#choosing-a-judge-and-a-threshold).
  * The Stop hook checks the uncommitted change only: a change the agent commits before it stops is not checked.
* **Eliminating Local CLI Cold-Start (`KLINT_JUDGE_MODE=local` vs. `kev.serve`)**: In `KLINT_JUDGE_MODE=local`, `klint` loads the open-weight checkpoint into memory once per CLI invocation (~3–5s startup for `kev-4b` on Apple Silicon). For instant startup across frequent runs, either use `jaredpalmer/kev-0.8b` or keep a persistent `kev.serve` process running in the background with `KLINT_JUDGE_MODE=remote`.
* **Directory Summary Confidence Calibration**: Because `klint-structure` evaluates compact AST metadata summaries rather than full source code bodies, `[FAIL]` confidence scores on directory rules are naturally more conservative (`20%–50%`) than file-level code rules (`70%–99%`).

## Roadmap & Upcoming Features

Shipped in this release: Python class and function units, change summaries read from git, the Claude Code Stop hook, and the hosted Jev judge.

1. **Git Diff Mode (`--diff`)**: Sub-second pre-commit and PR auditing targeting only modified files and diff hunks.
2. **MCP Server**: Exposing `klint` as a local MCP server so AI coding assistants (Claude Code, Cursor, Codex) can audit code in real time, and hooks for agents other than Claude Code.
3. **Multi-Language Extractors**: Class and function units, and `klint-structure` outlines, for TypeScript/JavaScript (`.ts`, `.tsx`) and Go.
4. **Inline GitHub PR Review Annotations**: Extending the GitHub Action with inline pull-request review comments on flagged line ranges.
5. **Permutation Calibration & Multi-Unit Batching**: Supporting `/v1/systemone/permute` debiasing on borderline findings and batching multiple small units per inference pass.
6. **Non-Code Files**: Auditing text documents, LaTeX and other writing.
7. **More Accurate Local Judges**: A hosted Kev-27B and a Kev-4B fine-tuned on labelled change summaries, scored on the same test set.

## Contributing

Contributions of all kinds—new language extractors, community rule packs, performance optimizations, or CI/editor integrations—are warmly welcomed! See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for the setup, the layout, the checks and how pull requests merge.

## License

Distributed under the Apache License 2.0. See `LICENSE` for more information.
