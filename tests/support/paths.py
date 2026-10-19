"""Where things live in the repo, and the snapshot comparison type."""

from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots"
RULE_PACKS = REPO_ROOT / "klint" / "resources" / "catalog" / "code"
REACT_RULE_PACK = RULE_PACKS / "typescript" / "react.json"
PYTHON_PROJECT_RULE_PACK = RULE_PACKS / "python" / "project_structure.json"
# The built-in packs, in the order klint merges them.
BUILT_IN_RULE_PACKS = (
    RULE_PACKS / "common" / "backend.json",
    REACT_RULE_PACK,
    RULE_PACKS / "common" / "structure.json",
    PYTHON_PROJECT_RULE_PACK,
)
# The built-in packs for a file whose language is not identified.
FALLBACK_RULE_PACKS = (
    RULE_PACKS / "common" / "backend.json",
    RULE_PACKS / "common" / "structure.json",
)
# The built-in list of programming languages and their file extensions.
DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS = (
    RULE_PACKS / "common" / "language_to_file_extensions.json"
)
# Relative to the repo root, so unit ids in output stay short; tests that use
# it run from there (see the in_repo_root fixture).
MOCK_PROJECT = Path("examples/mock_bad_project")

SnapshotAsserter = Callable[[str, str], None]
