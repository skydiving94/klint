# Kev Code Auditor

> The first declarative semantic linter and architectural auditor for local open-weight System One (kev) models.

`kev-code-auditor` bridges the gap between fast, rigid deterministic linters (like ESLint or Ruff) and slow, expensive generative LLM code reviewers. By leveraging TypeSafe’s System One (`/v1/systemone`) pointer-head specification, it checks files and codebases against default and custom JSON rule packs in a single forward pass with zero token-generation overhead.

---

## Why Kev Code Auditor?

* **Lightning Fast & Deterministic**: Evaluates architectural antipatterns in milliseconds per file via batched pointer-head classification rather than generating verbose prose.
* **Zero-Egress Local Privacy**: Run entirely offline on your local machine using open-weight models (kev-0.8b, kev-4b) via Hugging Face or kev.serve, ensuring proprietary code never leaves your network.
* **Declarative Plain-English Rules**: Define team-specific architectural rules or antipatterns using simple JSON configuration files—no complex AST or Semgrep DSL required.
* **Clean OOD Architecture**: Designed with strict separation of concerns, featuring pluggable unit extractors, rule loaders, and model evaluators (supporting both remote HTTP servers and in-process execution).

---

## Features

* **File & Recursive Directory Auditing**: Scan individual files or entire project directory trees concurrently.
* **Confidence Scoring**: Surface model probabilities and confidence thresholds (--min-confidence) to automatically filter out borderline findings.
* **Decent Default Antipattern Coverage**: Ships with default rules targeting backend antipatterns (N+1 queries, hardcoded secrets, tight coupling, god components) and React frontend antipatterns (prop drilling, improper state colocation, direct DOM manipulation).
* **Customizable Antipattern Rules**: Supports custom team-specific rules defined and loaded in JSON format.
---

## Installation & Setup

Prerequisites
* Python 3.13+
* Install `kev` (either for local in-process use or via kev.serve):
  ```
  pip install "kev[serve] @ git+https://github.com/jaredpalmer/kev.git"
  ```

Quickstart

1. Clone the repository:
   ```
   git clone https://github.com/skydiving94/kev-code-auditor.git
   cd kev-code-auditor
   ```

2. Configure your environment:
   Copy the example environment configuration into your `.env` and adjust as needed:
   
   Example .env for local serverless execution:
   ```
   KEV_MODE=local
   KEV_MODEL_NAME=jaredpalmer/kev-0.8b
   KEV_DEFAULT_RULES_PATH=./resources/default_rules.json
   ```

3. Run your first audit:
   Scan an example file or your entire source tree:
   ```
   python -m src.cli.basic_audit examples/
   ```

---

## Usage

Command-Line Interface

* Audit a single file or directory:
  ```
  python -m src.cli.basic_audit path/to/your/project/
  ```

* Use custom user-defined rules:
  ```
  python -m src.cli.basic_audit path/to/your/project/ --rules ./custom_rules.json
  ```

* Filter by confidence threshold:
  ```
  python -m src.cli.basic_audit path/to/your/project/ --min-confidence 0.80
  ```

* Output all judgments (Pass, Fail, Irrelevant):
  ```
  python -m src.cli.basic_audit path/to/your/project/ --all
  ```

---

## Project Structure

```
kev-code-auditor/
├── config/              # Dynamic environment configuration (AppSettings)
├── core/                # Pure domain models, entities, and ABC interfaces
├── infrastructure/      # Concrete implementations (WholeFileExtractor, JsonRuleLoader, Pretrained/InProcess Evaluators)
├── src/cli/             # Driving adapters (CLI app and its helpers, to be cleaned up)
├── resources/           # Default antipattern rules (default_rules.json)
└── examples/            # Sample files demonstrating rule detection
```
---

## Roadmap & Upcoming Features

* **Project-Level Structure Analysis**: Integrating Python doc/AST extractors to parse module-level documentation, class hierarchies, and cross-file dependencies to detect high-level architectural project antipatterns.
* **Git Diff Mode (--diff)**: Sub-second pre-commit hooks targeting only modified files.
* **Batch Optimization**: Advanced speculative fan-out for multi-rule single-pass evaluations.
* **Tech Debt Relief**: Cleaner code. 

---

## License

Distributed under the Apache License 2.0. See LICENSE for more information.