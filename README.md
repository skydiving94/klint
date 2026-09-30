# klint
> **Semantic code auditing at the speed of Ruff, with the depth of an LLM—at zero token-generation cost.**

`klint` bridges the gap between rigid, syntax-bound linters (like ESLint or Ruff) and slow, expensive LLM code reviewers (like PR bots streaming tokens for 40 seconds). 
By leveraging the **System One (`/v1/systemone`)** pointer-head specification, `klint` evaluates files and recursive package trees against custom JSON rule packs in a **single forward pass with zero decoded tokens**.

![klint CLI Output](docs/assets/cli-demo.png)

## Why klint?

* **Single-Pass, Zero-Generation Inference**: Evaluates an entire 16-rule pack in a single forward pass (~0.5s–2.5s per file locally on Apple Silicon MPS, or sub-second on CUDA / hosted `/v1/systemone`) rather than streaming hundreds of verbose reasoning tokens for 30+ seconds.
* **100% Local (`kev`) or Remote (`jev` / `kev.serve`)**: Run entirely offline on your machine using open-weight models (`kev-0.8b`, `kev-4b`) via Hugging Face, or point to any remote `/v1/systemone` endpoint (`jev` API or self-hosted `kev.serve`).
* **Declarative Plain-English Rules (`klint.json`)**: Define team-specific architectural rules or antipatterns using simple ESLint-style JSON configuration files—no complex AST or Semgrep DSL required.
* **Clean, Extensible Hexagonal Architecture**: Built with auto-registering `AuditableUnit` nodes, pluggable unit/metadata extractors, rule loaders, and model evaluators so enterprise teams can easily adapt it to any language stack or custom audit workflow.

### How klint Compares (Related Work)

| Tool Category                      | Examples                                   | Speed & Cost                                     | Privacy                                  | Architectural & Semantic Depth                                                                                                                                                        |
| :--------------------------------- | :----------------------------------------- | :----------------------------------------------- | :--------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Deterministic Linters**          | ESLint, Ruff, Pylint, Semgrep              | Instant, free                                    | 100% Local                               | **Syntax-bound**: Great for formatting and known AST patterns, but cannot judge domain cohesion, layering intent, or responsibility boundaries without brittle custom DSLs.           |
| **Generative LLM Reviewers**       | CodeRabbit, GPT/Claude PR Bots             | Slow (20–45s/file), high token cost              | Cloud API (typically)                    | **High, but noisy**: Understands semantics, but relies on slow, non-deterministic autoregressive token generation.                                                                    |
| **Other System One (`jev`) Tools** | `ErisLint`, `jgrep`, `patdown`, `jev-pref` | Fast (single forward pass)                       | Mostly Hosted `jev` API                  | **Flat file/diff scope**: Evaluates individual code chunks or diffs against rules, but lacks recursive package-tree modeling and native in-process `kev` execution.                   |
| **`klint`**                        | `klint`, `klint-project`                   | **Fast (single forward pass, 0 decoded tokens)** | **100% Local (`kev`) or Remote (`jev`)** | **File + Recursive Package Architecture**: Combines semantic code linting with composite Python AST directory trees, dependency rollups, and extensible `AuditableUnit` abstractions. |

## Features

* **File & Recursive Directory Auditing (`klint`)**: Scan individual source files or entire directory trees concurrently with live progress reporting and built-in concurrency throttling.
* **Recursive Python Project Structure Auditing (`klint-project`)**: Audit Python package and directory hierarchies layer-by-layer, combining AST-based file metadata extraction (`imports`, `exports`, `classes`, `functions`, `line_count`, `__init__.py` public API status) with recursive subpackage dependency rollups and mutual cycle detection.
* **4-Way Semantic Judgment & Confidence Sorting**: Classifies rules into `Pass`, `Fail`, `Irrelevant`, or `Lack of Evidence`, automatically sorting findings from highest confidence to lowest and supporting `--min-confidence` filtering.
* **Built-In Backend, React & Architectural Rule Packs**:
  * **File-level rules (`default_rules.json`)**: Python/backend rules (N+1 queries, hardcoded secrets, sync blocking I/O, missing input validation, tight coupling, god components) and React/TypeScript frontend rules (prop drilling, improper state colocation, direct DOM manipulation, overusing `useEffect`, missing hook dependency arrays).
  * **Project-level structure rules (`default_project_rules.json`)**: Circular package dependencies, hexagonal layering violations, god packages, junk-drawer modules, barrel-file sprawl, leaky abstractions, missing package public APIs, and business logic in presentation layers.

## Installation & Quickstart

### Prerequisites
* Python 3.11+
* Install `kev` (required for default local in-process inference or local `kev.serve`):
  ~~~bash
  pip install "kev[serve] @ git+https://github.com/jaredpalmer/kev.git"
  ~~~

### Zero-Config Quickstart
1. Clone and install `klint`:
   ~~~bash
   git clone https://github.com/skydiving94/klint.git
   cd klint
   pip install -e .
   ~~~

2. Run your first file or project audit immediately (defaults to local in-process `jaredpalmer/kev-4b`):
   ~~~bash
   # Audit a file or directory against file-level code rules
   klint examples/backend_data_and_security.py

   # Audit a Python package tree for architectural & layering violations
   klint-project examples/mock_bad_project/
   ~~~

## Usage

### 1. File & Codebase Audit (`klint`)
* Audit a single file or entire directory tree (visual CLI report sorted by confidence):
  ~~~bash
  klint examples/
  ~~~
* Filter by minimum confidence threshold (`0.0` to `1.0`):
  ~~~bash
  klint examples/backend_data_and_security.py --min-confidence 0.65
  ~~~
* Output all judgments (`Pass`, `Fail`, `Irrelevant`, `Lack of Evidence`):
  ~~~bash
  klint examples/ --all
  ~~~
* Output machine-readable JSON (for CI/CD pipelines or scripts):
  ~~~bash
  klint examples/ --json
  ~~~

### 2. Recursive Project Structure Audit (`klint-project`)
* Audit a Python project directory and all nested subpackages layer-by-layer:
  ~~~bash
  klint-project examples/mock_bad_project/
  ~~~
* Filter project findings by confidence threshold or emit raw JSON:
  ~~~bash
  klint-project src/ --min-confidence 0.25 --json
  ~~~

### 3. GitHub Actions CI/CD Integration
You can run `klint` or `klint-project` directly in your GitHub Actions workflows:

~~~yaml
- name: Run klint Architectural Audit
  uses: skydiving94/klint@main
  with:
    target: "src/"
    mode: "file"                        # "file" (klint) or "project" (klint-project)
    min_confidence: "0.65"
    kev_mode: "local"                   # Or "remote" with kev_base_url / kev_api_key
    kev_model_name: "jaredpalmer/kev-4b"
~~~

## Configuration & Custom Rules (`klint.json`)

Like ESLint, `klint` works out of the box from any directory on your machine and automatically discovers a **`klint.json`** (or **`.klintrc.json`**) file in the target project root. You can also pass any custom JSON file explicitly via `--rules ./custom_rules.json`.

### Defining Custom Rules & Model Settings in `klint.json`
Because `klint` evaluates whether code **follows** a practice (`Pass`) or **violates** it (`Fail`), always phrase `"instructions"` as a positive practice: **`"<positive practice> rather than <antipattern>?"`**.

~~~json
{
  "env": {
    "KEV_MODE": "local",
    "KEV_MODEL_NAME": "jaredpalmer/kev-4b"
  },
  "rules": {
    "no_raw_print_statements": {
      "type": "choice",
      "instructions": "Does the code use a structured logger rather than raw print() statements for application logging?",
      "target_unit_types": ["file"]
    },
    "domain_purity": {
      "type": "choice",
      "instructions": "Does the core domain package remain free of database ORM and HTTP framework imports rather than coupling domain entities to infrastructure?",
      "target_unit_types": ["project_directory"]
    }
  }
}
~~~

### Switching Between Local `kev` and Remote `jev` / `kev.serve`
You can configure `klint` via shell environment variables (`export KEV_...`), the `"env"` block in your project's `klint.json`, or (for `klint` contributors/local repo development) by copying `.env.example` to `.env` inside the `klint` repository:

* **Local Serverless Mode (Default — In-Process Open-Weight `kev`)**:
  ~~~env
  KEV_MODE=local
  KEV_MODEL_NAME=jaredpalmer/kev-4b
  ~~~
* **Remote Server Mode (`jev` Cloud API or Persistent Local `kev.serve`)**:
  ~~~env
  KEV_MODE=remote
  KEV_BASE_URL=http://127.0.0.1:8009
  KEV_MODEL_NAME=kev-latest
  KEV_API_KEY=your-secret-key-if-enabled
  ~~~

* **Configuration Precedence**: Exported shell variables (`export KEV_...`) $\rightarrow$ Target project `klint.json` `"env"` block $\rightarrow$ `klint` repo `.env` (dev override) $\rightarrow$ Built-in defaults.
* **Merge vs. Replace Rules**: Custom rules in `klint.json` or `--rules` merge with built-in rules (overriding any rule with the same ID). To replace built-in rule packs completely, set `KEV_DEFAULT_RULES_PATH` or `KEV_DEFAULT_PROJECT_RULES_PATH`.

## Enterprise Extensibility: Custom Auditable Units & Extractors

`klint` uses a hexagonal architecture where any custom unit subclassing `AuditableUnit` automatically registers its `unit_type` via `__init_subclass__` for immediate use in JSON rules:

1. **Define a Custom `AuditableUnit`** (e.g., for SQL migrations, Terraform modules, or AST functions):
   ~~~python
   from dataclasses import dataclass
   from typing import Any, ClassVar, Dict
   from src.core.domain.units.base import AuditableUnit

   @dataclass(frozen=True)
   class AuditableSqlMigrationUnit(AuditableUnit):
       unit_type: ClassVar[str] = "sql_migration"  # Auto-registered for JSON "target_unit_types"
       sql_text: str = ""

       def get_content(self) -> str:
           return self.sql_text

       def get_metadata(self) -> Dict[str, Any]:
           return {"migration_id": self.unit_id}
   ~~~
2. **Implement a `BaseUnitExtractor` (or `BaseFileMetadataExtractor`)**:
   ~~~python
   from pathlib import Path
   from typing import List
   from src.core.domain.units import AuditableUnit
   from src.core.interfaces.extractor import BaseUnitExtractor

   class SqlMigrationExtractor(BaseUnitExtractor):
       async def extract(self, target: Path) -> List[AuditableUnit]:
           return [AuditableSqlMigrationUnit(unit_id=str(target), sql_text=target.read_text())]
   ~~~
3. **Wire into `AuditService`**: Pass your extractor into `AuditService(extractor=SqlMigrationExtractor(), evaluator=..., rule_loader=...)`—no changes to the core evaluation engine required.

## Current Limitations (v0.1) & Performance Tips

* **Raw-Text File Audit (`klint`) vs. Python-Only AST Project Audit (`klint-project`)**:
  * `klint` (`WholeFileExtractor`) reads raw source text without an AST parser, so it evaluates any text-based source file (the built-in `default_rules.json` ships with rules for **Python** and **React/TypeScript**; other languages can be targeted via custom rules in `klint.json`).
  * `klint-project` (`PythonFileMetadataExtractor`) relies on Python's `ast` module to extract `imports`, `exports`, `classes`, and `functions`, so deep structural extraction currently supports **Python (`.py`)** files only (non-Python files fall back to file names and line counts until multi-language AST extractors land).
* **Whole-File Context Window (`klint`)**: Because `klint` currently passes entire files as a single unit (`lines 1-N`) and small System One models (`kev-0.8b`, `kev-4b`) achieve peak accuracy on compact contexts (`<512` tokens), large files (`>300–500` lines) can experience lower confidence scores until AST component slicing (Roadmap #1) is enabled.
* **Eliminating Local CLI Cold-Start (`KEV_MODE=local` vs. `kev.serve`)**: In `KEV_MODE=local`, `klint` loads the open-weight checkpoint into memory once per CLI invocation (~3–5s startup for `kev-4b` on Apple Silicon). For instant startup across frequent runs, either use `jaredpalmer/kev-0.8b` or keep a persistent `kev.serve` process running in the background with `KEV_MODE=remote`.
* **Directory Summary Confidence Calibration**: Because `klint-project` evaluates compact AST metadata summaries rather than full source code bodies, `[FAIL]` confidence scores on directory rules are naturally more conservative (`20%–50%`) than file-level code rules (`70%–99%`).

## Roadmap & Upcoming Features

1. **Recursive Code Component Analysis & Context-Window Slicing**: Extracting granular AST units (`AuditablePythonClassUnit`, `AuditablePythonFunctionUnit`) so every unit stays inside `kev`'s high-accuracy `<512` token sweet spot while reporting exact method-level line numbers.
2. **Git Diff Mode (`--diff`)**: Sub-second pre-commit and PR auditing targeting only modified files and diff hunks.
3. **Claude Code Hooks & MCP Server Integration**: Exposing `klint` as a deterministic agent supervision hook and local MCP server so AI coding assistants (Claude Code, Cursor, Codex) can audit code in real time.
4. **Multi-Language AST Metadata Extractors**: Extending `BaseFileMetadataExtractor` to support TypeScript/JavaScript (`.ts`, `.tsx`) and Go for `klint-project`.
5. **Inline GitHub PR Review Annotations**: Extending the GitHub Action with `--fail-on-issues` gating and inline pull-request review comments on flagged line ranges.
6. **Permutation Calibration & Multi-Unit Batching**: Supporting `/v1/systemone/permute` debiasing on borderline findings and batching multiple small units per inference pass.
7. **Multi Media Auditing**: Supporting parsing and analyzing text files, latex etc. as writing assistant.
## Contributing: Getting Started Guide

Contributions of all kinds—new language AST extractors, community rule packs, performance optimizations, or CI/editor integrations—are warmly welcomed!

### 1. Repository Architecture (`src/`)
`klint` follows a strict hexagonal (ports & adapters) architecture. When contributing, keep `src/core/` pure and free of external I/O or ML framework imports:

~~~text
├── resources/                  # Built-in JSON rule packs (default_rules.json, default_project_rules.json)
├── examples/                   # Antipattern test files (.py, .tsx) & mock_bad_project/ verification suite
└── src/
    ├── config/settings.py      # 4-tier config loader (Shell Env -> klint.json -> .env -> Defaults)
    ├── core/                   # Pure domain layer (no external I/O or ML dependencies)
    │   ├── domain/             # Judgment & QuestionType enums, AuditRule, AuditReport, and AuditableUnit nodes
    │   ├── interfaces/         # Abstract ports: BaseUnitExtractor, BaseFileMetadataExtractor, BaseKevEvaluator, BaseRuleLoader
    │   └── services/           # AuditService orchestrating concurrent extraction and rule evaluation
    ├── infrastructure/         # Concrete adapter implementations
    │   ├── extractors/         # WholeFileExtractor, PythonFileMetadataExtractor, RecursiveProjectExtractor
    │   ├── kev/                # InProcessKevEvaluator (local kev) & PretrainedKevEvaluator (remote /v1/systemone)
    │   └── rules/              # JsonRuleLoader with caching and unit-type validation
    └── cli/                    # CLI entrypoints (basic_audit.py, project_audit.py), DI factory, and terminal formatter
~~~

*Note that currently the project is still in early development, so the architecture above is subject to change.*
*If you have any input on making it more structured and maintainable, that is very much welcomed!*

### 2. Local Development Setup
1. Fork and clone the repository, then install in editable mode:
   ~~~bash
   pip install -e .
   ~~~
2. (Optional) Copy `.env.example` to `.env` if you want to override your local default model (e.g., switching to `jaredpalmer/kev-0.8b` for faster local iteration):
   ~~~bash
   cp .env.example .env
   ~~~

### 3. Common Contribution Workflows
* **Adding or Refining Built-In Rules**:
  * Edit `resources/default_rules.json` (file-level rules) or `resources/default_project_rules.json` (project-structure rules).
  * Always phrase `"instructions"` as a positive practice (`"<positive practice> rather than <antipattern>?"`) and include `"target_unit_types"`.
* **Adding a New Language AST Extractor for `klint-project`**:
  1. Subclass `BaseFileMetadataExtractor` in `src/infrastructure/extractors/file_metadata_extractor.py` (implementing `supports(path)` and `extract_file(path) -> AuditableFileMetadataUnit`).
  2. Register your extractor in `RecursiveProjectExtractor.__init__()` inside `src/infrastructure/extractors/project_extractor.py` before `FallbackFileMetadataExtractor()`.
* **Testing Your Changes Before Opening a PR**:
  Run both CLI entrypoints against the built-in test suites to verify there are no regressions:
  ~~~bash
  # 1. Verify file-level auditing across Python & React/TypeScript examples
  klint examples/

  # 2. Verify recursive project-structure auditing & cycle detection
  klint-project examples/mock_bad_project/
  ~~~

## License

Distributed under the Apache License 2.0. See `LICENSE` for more information.
