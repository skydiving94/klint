## Plan

The refactoring focuses strictly on decoupling the domain models and preparing the architecture for **Feature 1 (Recursive Project Structure Audit)** and **Feature 2 (Recursive Code Component Audit)** without altering current CLI behavior or introducing premature feature implementations:

1. **Eliminate the God `models.py` Module:** Split `src/core/domain/models.py` into cohesive, single-purpose domain modules (`rule.py`, `report.py`, and a `units/` subpackage) where every file stays well under 100 lines.


2. **AST-Style Composite `AuditableUnit` Hierarchy:**
* Convert `AuditableUnit` into a pure ABC in `src/core/domain/units/base.py` that only requires `unit_id: str`, `unit_type: UnitType`, and an abstract `get_content() -> str` method. Concrete file/line fields (`content`, `file_path`, `start_line`, `end_line`) move to `AuditableFileUnit` in `src/core/domain/units/file.py`, resolving the `AuditableUnit` `FIXME`.


* **AST Composition for Future Units:** Following an AST mental model, any composite unit—such as a future `AuditablePythonModuleUnit` (composed of `AuditablePythonClassUnit`, `AuditablePythonFunctionUnit`, etc., where classes in turn compose `AuditablePythonMethodUnit` and `AuditablePythonClassFieldUnit`) or `AuditableProjectDirectoryUnit` (composed of sub-packages and `AuditableFileMetadataUnit`s)—implements `get_content() -> str` by aggregating its own metadata and recursively calling `child.get_content()` across its child units. Because the root unit's `get_content()` encapsulates the auditable representation of its subtree (and sub-units can also be emitted directly by component extractors when granular evaluation is desired), `AuditService.run_audit()` remains clean and unchanged.




3. **Multi-Tier Extractor Hierarchy:**
* Keep `BaseUnitExtractor` and `WholeFileExtractor` as the only active classes for this pass.


* Design the package layout so future extractors branch cleanly into two tiers under `BaseUnitExtractor`:
* **Project Structure Tier:** `BaseUnitExtractor` $\rightarrow$ `BaseRecursiveProjectExtractor` $\rightarrow$ `RecursivePythonProjectExtractor` (extracts recursive package/directory trees and module-level metadata).
* **Code Component Tier:** `BaseUnitExtractor` $\rightarrow$ `BaseFileComponentExtractor` $\rightarrow$ `PythonComponentExtractor` (extracts nested AST components within a file).




4. **Enforce `QuestionType` Enum:** Add `QuestionType(str, Enum)` in `src/core/domain/enums.py` and update `AuditRule` and `JsonRuleLoader` to use it, resolving the second `FIXME` in `models.py`.



---

## Proposed structure

Files marked **new**, **reworked**, or **updated (imports)** are included in the code changes below; files marked *(planned)* show the complete Python target architecture for Features 1 & 2 with each module scoped under 100 lines:

* `src/`
  * `cli/`
    * `basic_audit.py` — *unchanged*
    * `factory.py` — *unchanged*
    * `file_collector.py` — *unchanged*
  * `config/`
    * `settings.py` — *unchanged*
  * `core/`
    * `domain/`
      * `enums.py` — **reworked** (adds `QuestionType` enum)
      * `rule.py` — **new** (`AuditRule`)
      * `report.py` — **new** (`AuditFinding`, `AuditReport`)
      * `units/` — **new package**
        * `__init__.py` — **new** (re-exports `AuditableUnit`, `AuditableFileUnit`)
        * `base.py` — **new** (`AuditableUnit` ABC with `get_content() -> str`)
        * `file.py` — **new** (`AuditableFileUnit`)
        * `project.py` — *(planned - Feature 1: `AuditableProjectDirectoryUnit`, `AuditableFileMetadataUnit`)*
        * `python_units/`
          * `python_module.py` — *(planned - Feature 2: `AuditablePythonModuleUnit`, `AuditablePythonImportUnit`, `AuditablePythonConstantUnit`)*
          * `python_class.py` — *(planned - Feature 2: `AuditablePythonClassUnit`, `AuditablePythonClassFieldUnit`)*
          * `python_function.py` — *(planned - Feature 2: `AuditablePythonFunctionUnit`, `AuditablePythonMethodUnit`, `AuditablePythonDecoratorUnit`)*
  * `interfaces/`
    * `extractor.py` — **updated (imports)** (`BaseUnitExtractor`; will later host `BaseRecursiveProjectExtractor` and `BaseFileComponentExtractor`)
    * `evaluator.py` — **updated (imports)**
    * `rule_loader.py` — **updated (imports)**
  * `services/`
    * `audit_service.py` — **updated (imports)**
  * `infrastructure/`
    * `extractors/`
      * `file_extractor.py` — **reworked** (`WholeFileExtractor` returns `AuditableFileUnit`)
      * `project/` — *(planned - Feature 1)*
        * `base_project_extractor.py` — *(planned: directory walk & language dispatcher)*
        * `python_project_extractor.py` — *(planned: `RecursivePythonProjectExtractor`)*
    * `components/` — *(planned - Feature 2)*
      * `python_component_extractor.py` — *(planned: `PythonComponentExtractor`)*
  * `kev/`
    * `pretrained.py` — **reworked** (calls `unit.get_content()` instead of reading `unit.content`)
    * `in_process.py` — **reworked** (calls `unit.get_content()` instead of reading `unit.content`)
  * `rules/`
    * `json_loader.py` — **reworked** (parses `QuestionType` enum)

