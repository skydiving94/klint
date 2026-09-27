# klint

> The first declarative semantic linter and architectural code auditor for local open-weight System One (`kev`) models.

`klint` bridges the gap between fast, rigid deterministic linters (like ESLint or Ruff) and slow, expensive generative LLM code reviewers. By leveraging TypeSafe's System One (`/v1/systemone`) pointer-head specification, it checks files and codebases against default and custom JSON rule packs in a single forward pass with zero token-generation overhead.

## Why klint?

* **Lightning Fast & Deterministic**: Evaluates architectural antipatterns in milliseconds per file via batched pointer-head classification rather than generating verbose prose.
* **Zero-Egress Local Privacy**: Run entirely offline on your local machine using open-weight models (`kev-0.8b`, `kev-4b`) via Hugging Face or `kev.serve`, ensuring proprietary code never leaves your network.
* **Declarative Plain-English Rules**: Define team-specific architectural rules or antipatterns using simple JSON configuration files—no complex AST or Semgrep DSL required.
* **Clean, Extensible OOD Architecture**: Designed with strict hexagonal separation of concerns—featuring auto-registering `AuditableUnit` nodes, pluggable unit/metadata extractors, rule loaders, and model evaluators—making it effortless to adapt to any team's language stack or custom audit workflow.

### How klint Compares (Related Work)

| Tool Category                      | Examples                                     | Speed & Cost                           | Privacy                                  | Architectural & Semantic Depth                                                                                                                                                                |
| :--------------------------------- | :------------------------------------------- | :------------------------------------- | :--------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Deterministic Linters**          | ESLint, Ruff, Pylint, Semgrep                | Instant, free                          | 100% Local                               | **Syntax-bound**: Great for formatting and known AST patterns, but cannot judge domain cohesion, layering intent, or responsibility boundaries without brittle custom DSLs.                   |
| **Generative LLM Reviewers**       | CodeRabbit, GPT/Claude PR Bots               | Slow (seconds/file), high token cost   | Cloud API (typically)                    | **High, but noisy**: Understands semantics, but relies on slow, non-deterministic autoregressive token generation.                                                                            |
| **Early System One (`jev`) Tools** | `ErisLint`, `jgrep`, `jev-review`, `jev-git` | Milliseconds (single forward pass)     | Mostly Hosted `jev` API                  | **Flat file/diff scope**: Evaluates individual code chunks or diffs against plain-English rules or fixed rubrics, but lacks recursive package-tree modeling and native local `kev` execution. |
| **`klint`**                        | `basic_audit`, `project_audit`               | **Milliseconds (single forward pass)** | **100% Local (`kev`) or Remote (`jev`)** | **File + Recursive Package Architecture**: Combines whole-file semantic linting with composite AST directory trees, dependency rollups, and extensible `AuditableUnit` abstractions.          |

* **Versus Traditional Linters (`Ruff`, `ESLint`, `Semgrep`)**: Traditional linters check *how* code is formatted or match rigid syntax trees. `klint` evaluates *architectural intent*—catching god components, leaky domain abstractions, business logic in presentation layers, and circular subpackage dependencies using plain-English JSON rules.
* **Versus Generative LLM Code Reviewers**: Generative reviewers must stream hundreds of reasoning tokens per file. `klint` uses System One (`/v1/systemone`) pointer-head classification to score an entire rule pack in a single forward pass with calibrated probabilities (`Pass`, `Fail`, `Irrelevant`, `Lack of Evidence`).
* **Versus Other System One / `jev` Projects (`ErisLint`, `jgrep`, `jev-review`)**: While early `/v1/systemone` tools focus on flat file chunks, git diffs, or hosted `jev` APIs, `klint` is built natively for both serverless local open-weight `kev` models (`InProcessKevEvaluator`) and remote servers (`PretrainedKevEvaluator`), and introduces recursive, layer-by-layer package structure auditing (`AuditableProjectDirectoryUnit`) on top of an extensible object-oriented unit hierarchy.

## Features

* **File & Recursive Directory Auditing**: Scan individual files or entire project directory trees concurrently via `basic_audit`.
* **Recursive Project Structure Auditing**: Audit package and directory hierarchies layer-by-layer via `project_audit`, combining extensible AST-based file metadata extraction (`imports`, `exports`, `classes`, `functions`, `line_count`) with recursive subpackage dependency rollups and cycle detection.
* **4-Way Semantic Judgment & Confidence Scoring**: Classifies rules into `Pass`, `Fail`, `Irrelevant`, or `Lack of Evidence`, surfacing model probabilities and confidence thresholds (`--min-confidence`) to automatically filter out borderline findings.
* **Decent Default Antipattern Coverage**: Ships with default file-level rules (`default_rules.json`) targeting backend antipatterns (N+1 queries, hardcoded secrets, sync blocking I/O, tight coupling, god components) and React frontend antipatterns (prop drilling, improper state colocation, direct DOM manipulation), plus project-level structure rules (`default_project_rules.json`) targeting architectural antipatterns (circular package dependencies, layering violations, god packages, junk-drawer modules, trivial subpackages, leaky abstractions).
* **Customizable Antipattern Rules**: Supports custom team-specific rules defined and loaded in JSON format with automatic `target_unit_types` validation.
* **Extensible Units & Custom Audit Workflows**: Built on a plug-and-play OOD hierarchy where teams can subclass `AuditableUnit` (auto-registered via `__init_subclass__`), implement custom `BaseUnitExtractor` or `BaseFileMetadataExtractor` strategies for new languages, and model custom audit scripts after `basic_audit.py` and `project_audit.py` without modifying the core `AuditService` engine.

## Installation & Setup

### Prerequisites

* Python 3.13+
* Install `kev` (either for local in-process use or via `kev.serve`):
  ~~~bash
  pip install "kev[serve] @ git+https://github.com/jaredpalmer/kev.git"
  ~~~

### Quickstart

1. Clone the repository:
   ~~~bash
   git clone https://github.com/skydiving94/klint.git
   cd klint
   ~~~

2. Configure your environment:
   Copy the example environment configuration into your `.env` and adjust as needed:
   ~~~env
   KEV_MODE=local
   KEV_MODEL_NAME=jaredpalmer/kev-4b
   KEV_DEFAULT_RULES_PATH=./resources/default_rules.json
   KEV_DEFAULT_PROJECT_RULES_PATH=./resources/default_project_rules.json
   ~~~

3. Run your first audit:
   Scan an example file or directory for code-level antipatterns:
   ~~~bash
   python -m src.cli.basic_audit examples/
   ~~~
   Or run a recursive project structure audit across a source tree:
   ~~~bash
   python -m src.cli.project_audit src/
   ~~~

## Usage

### Command-Line Interface

#### File & Codebase Audit (`basic_audit`)

* Audit a single file or directory:
  ~~~bash
  python -m src.cli.basic_audit path/to/your/project/
  ~~~
* Use custom user-defined rules:
  ~~~bash
  python -m src.cli.basic_audit path/to/your/project/ --rules ./custom_rules.json
  ~~~
* Filter by confidence threshold:
  ~~~bash
  python -m src.cli.basic_audit path/to/your/project/ --min-confidence 0.80
  ~~~
* Output all judgments (`Pass`, `Fail`, `Irrelevant`, `Lack of Evidence`):
  ~~~bash
  python -m src.cli.basic_audit path/to/your/project/ --all
  ~~~

#### Recursive Project Structure Audit (`project_audit`)

* Audit a project directory and all nested subpackages layer-by-layer:
  ~~~bash
  python -m src.cli.project_audit path/to/your/project/
  ~~~
* Use custom project structure rules:
  ~~~bash
  python -m src.cli.project_audit path/to/your/project/ --rules ./custom_project_rules.json
  ~~~
* Filter project findings by confidence threshold or output all judgments:
  ~~~bash
  python -m src.cli.project_audit path/to/your/project/ --min-confidence 0.30 --all
  ~~~

## Project Structure

### Source Code (`src/`)

* **`config/`**: Dynamic environment configuration
  * `settings.py`: Environment loader and `AppSettings` configuration model
* **`core/`**: Pure domain models, entities, and abstract interfaces
  * **`domain/`**: Core domain entities and value objects
    * `enums.py`: `Judgment` (with natural-language criteria) and `QuestionType` enums
    * `rule.py`: `AuditRule` domain model and unit applicability logic
    * `report.py`: `AuditFinding` and `AuditReport` aggregation models
    * **`units/`**: Composite `AuditableUnit` hierarchy
      * `__init__.py`: Public package exports for domain unit classes
      * `base.py`: `AuditableUnit` ABC with automatic `unit_type` subclass registration
      * `file.py`: `AuditableFileUnit` and `FileUnitMetadata` for whole-file evaluation
      * `file_metadata.py`: `AuditableFileMetadataUnit` and `FileMetadataPayload` for structural file summaries
      * `project_directory.py`: `AuditableProjectDirectoryUnit` and `ProjectDirectoryUnitMetadata` for recursive package trees
  * **`interfaces/`**: Abstract ports for infrastructure adapters
    * `extractor.py`: `BaseUnitExtractor` and `BaseFileMetadataExtractor` ABCs
    * `evaluator.py`: `BaseKevEvaluator` ABC
    * `rule_loader.py`: `BaseRuleLoader` ABC
  * **`services/`**: Application business logic
    * `audit_service.py`: `AuditService` orchestrating concurrent unit extraction and rule evaluation
* **`infrastructure/`**: Concrete adapter implementations
  * **`extractors/`**: Code and project metadata extractors
    * `file_extractor.py`: `WholeFileExtractor` for reading raw source files
    * `file_metadata_extractor.py`: `PythonFileMetadataExtractor` (AST-based) and `FallbackFileMetadataExtractor`
    * `project_extractor.py`: `RecursiveProjectExtractor` for building composite directory trees
  * **`kev/`**: System One model evaluators
    * `pretrained.py`: `PretrainedKevEvaluator` for remote `/v1/systemone` HTTP inference
    * `in_process.py`: `InProcessKevEvaluator` for local serverless execution via `kev.serve`
  * **`rules/`**: Rule loading adapters
    * `json_loader.py`: `JsonRuleLoader` with caching and `target_unit_types` validation
* **`cli/`**: Driving CLI adapters (to be cleaned up)
  * `basic_audit.py`: CLI entrypoint (`CLIApp`) for file and recursive file-tree audits
  * `project_audit.py`: CLI entrypoint (`ProjectAuditCLIApp`) for layer-by-layer project structure audits
  * `factory.py`: Dependency injection wiring (`create_audit_service`, `create_project_audit_service`)
  * `file_collector.py`: File and directory discovery helpers (`collect_target_files`, `collect_target_directories`)

### Rule Packs & Examples

* **`resources/`**: Built-in declarative JSON rule packs
  * `default_rules.json`: Default file-level backend and React frontend antipattern rules
  * `default_project_rules.json`: Default project-level architectural and package-structure rules
* **`examples/`**: Sample code files demonstrating antipattern detection
  * `backend_data_and_security.py` & `backend_io_and_coupling.py`: Python backend antipatterns
  * `frontend_architecture.tsx` & `frontend_hooks_and_dom.tsx`: React/TypeScript frontend antipatterns

## Update

### September 27, 2026

#### Domain Architecture Refactoring
* Decomposed the monolithic `models.py` into focused domain modules (`enums.py`, `rule.py`, `report.py`, and `src/core/domain/units/`) with each module scoped under 100 lines.
* Converted `AuditableUnit` into an abstract base class (`src/core/domain/units/base.py`) with `get_content() -> str`, `get_metadata() -> Dict[str, Any]`, and automatic `unit_type` subclass registration via `__init_subclass__`.
* Added 4-way `Judgment` classification (`Pass`, `Fail`, `Irrelevant`, `Lack of Evidence`) with centralized natural-language criterion descriptions (`Judgment.as_criteria_payload()`) and `QuestionType` enum enforcement.

#### Recursive Project Structure Audit (Feature 1)
* Added `AuditableFileMetadataUnit` and `AuditableProjectDirectoryUnit` to represent file-level structural metadata and recursive package/directory trees.
* Added `BaseFileMetadataExtractor`, `PythonFileMetadataExtractor` (extracting line counts, `__all__` exports, imports, classes, and functions via Python's `ast` module), and `FallbackFileMetadataExtractor`.
* Added `RecursiveProjectExtractor` with subpackage dependency rollups and mutual subpackage cycle detection (`Mutual Subpackage Cycles`).
* Added the `src/cli/project_audit.py` CLI entrypoint, `collect_target_directories`, and `KEV_DEFAULT_PROJECT_RULES_PATH` configuration support in `AppSettings` and `factory.py`.

#### Rule Pack Additions & Refinements
* Added `resources/default_project_rules.json` with 18 architectural and project-structure rules (`god_package`, `junk_drawer_module`, `flat_structure`, `excessive_nesting_depth`, `inconsistent_naming_convention`, `trivial_subpackage`, `test_structure_mismatch`, `barrel_file_sprawl`, `circular_package_dependencies`, `layering_violation`, `god_file_or_class`, `duplicate_modules`, `leaky_abstraction`, `business_logic_in_presentation_layer`, `dead_code_module`, `missing_package_public_api`, `scattered_feature_logic`, `inconsistent_architectural_style`).
* Refined both `default_rules.json` and `default_project_rules.json` to follow a consistent positive-practice vs. antipattern phrasing (`"<positive practice> rather than <antipattern>"`).

## Roadmap & Upcoming Features

* **MCP Server Integration (Model Context Protocol)**: Exposing `klint` as a local MCP server so AI coding assistants (like Claude Code, Cursor, and Codex) can dynamically audit files and subpackages in real-time during agentic workflows.
* **GitHub Actions Integration (`klint-action`)**: Building a zero-friction CI/CD action to automatically scan pull requests for architectural layering violations and circular package dependencies.
* **Recursive Code Component Analysis (Feature 2)**: Integrating granular Python AST component extractors (`AuditablePythonModuleUnit`, `AuditablePythonClassUnit`, `AuditablePythonFunctionUnit`) to inspect class methods, fields, and decorators.
* **Multi-Language Metadata Extractors**: Extending `BaseFileMetadataExtractor` to support TypeScript/JavaScript and other languages.
* **Git Diff Mode (`--diff`)**: Sub-second pre-commit hooks targeting only modified files.
* **Batch Optimization**: Advanced speculative fan-out for multi-rule single-pass evaluations.

## Contributing & Crowdsourcing

`klint` is an open-source community initiative, and contributions of all kinds are warmly welcomed! Whether you want to add new language extractors, propose custom architectural rule packs (`default_rules.json` / `default_project_rules.json`), optimize inference batching, or build editor/CI integrations, feel free to open an issue or submit a pull request to help make local System One auditing better for everyone.

## License

Distributed under the Apache License 2.0. See `LICENSE` for more information.