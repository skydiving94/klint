"""Where things live in the repo, and the snapshot comparison type."""

from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots"
RULE_PACKS = REPO_ROOT / "src" / "resources" / "catalog" / "code"
# The built-in file-audit packs, in the order klint loads them.
DEFAULT_RULE_PACKS = (
    RULE_PACKS / "common" / "backend.json",
    RULE_PACKS / "typescript" / "react.json",
    RULE_PACKS / "common" / "structure.json",
)
DEFAULT_PROJECT_RULES = RULE_PACKS / "python" / "project_structure.json"
# Relative to the repo root, so unit ids in output stay short; tests that use
# it run from there (see the in_repo_root fixture).
MOCK_PROJECT = Path("examples/mock_bad_project")

SnapshotAsserter = Callable[[str, str], None]
