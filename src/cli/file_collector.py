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
    "dist",
    "build",
}
IGNORED_FILES = {
    ".DS_Store",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
}
IGNORED_SUFFIXES = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin", ".zip",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf",
    ".db", ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".mov", ".tar", ".gz", ".whl", ".pt", ".safetensors",
}


def _is_likely_binary(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(1024)
        return b"\x00" in chunk
    except OSError:
        return True


def collect_target_files(target: Path) -> List[Path]:
    if not target.exists():
        raise FileNotFoundError(f"Audit target does not exist: {target}")
    if target.is_file():
        return [target]
    return [
        p
        for p in sorted(target.rglob("*"))
        if p.is_file()
        and p.name not in IGNORED_FILES
        and not any(part in IGNORED_DIRS for part in p.parts)
        and p.suffix.lower() not in IGNORED_SUFFIXES
        and not _is_likely_binary(p)
    ]


def collect_target_directories(target: Path) -> List[Path]:
    if not target.exists():
        raise FileNotFoundError(
            f"Project structure audit target does not exist: {target}"
        )
    if not target.is_dir():
        raise ValueError(
            f"Project structure audit target must be a directory: {target}"
        )
    directories: List[Path] = [target]
    for p in sorted(target.rglob("*")):
        if p.is_dir() and not any(part in IGNORED_DIRS for part in p.parts):
            directories.append(p)
    return directories
