from pathlib import Path
from typing import List

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".vscode",
    ".idea",
}

IGNORED_FILES = {
    ".DS_Store",
}

IGNORED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".zip",
}


def collect_target_files(target: Path) -> List[Path]:
    if target.is_file():
        return [target]
    return [
        p
        for p in sorted(target.rglob("*"))
        if p.is_file()
        and p.name not in IGNORED_FILES
        and not any(part in IGNORED_DIRS for part in p.parts)
        and p.suffix.lower() not in IGNORED_SUFFIXES
    ]


def collect_target_directories(target: Path) -> List[Path]:
    if not target.is_dir():
        raise ValueError(
            f"Project structure audit target must be a directory: {target}")
    directories: List[Path] = [target]
    for p in sorted(target.rglob("*")):
        if p.is_dir() and not any(part in IGNORED_DIRS for part in p.parts):
            directories.append(p)
    return directories
