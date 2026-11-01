"""Finding the modules a source file imports, in any common language."""

import re
from collections.abc import Iterator

# `import a.b, c` and `from a.b import c`, each at the start of a line.
_LINE_IMPORT_PATTERNS = (
    re.compile(r"^\s*import\s+([A-Za-z_][\w.]*(?:\s*,\s*[A-Za-z_][\w.]*)*)", re.M),
    re.compile(r"^\s*from\s+([A-Za-z_][\w.]*)\s+import\b", re.M),
)
# `... from 'x'`, `import 'x'`, `require('x')` and `import('x')`.
_QUOTED_IMPORT_PATTERNS = (
    re.compile(r"\bfrom\s+['\"]([^'\"\s]+)['\"]"),
    re.compile(r"\bimport\s+['\"]([^'\"\s]+)['\"]"),
    re.compile(r"\b(?:require|import)\(\s*['\"]([^'\"\s]+)['\"]\s*\)"),
)


def find_imported_modules(text: str) -> set[str]:
    """Return the modules ``text`` imports, by every name they may be known by.

    A dotted module such as "a.b.c" is given as "a", "a.b" and "a.b.c". A
    package path such as "@scope/name/sub" is given as "@scope/name" and
    "@scope/name/sub", and "name/sub" as "name" and "name/sub". Relative
    imports are left out.
    """
    module_names: set[str] = set()
    for pattern in _LINE_IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            for module in match.group(1).split(","):
                module_names.update(_list_dotted_prefixes(module.strip()))
    for pattern in _QUOTED_IMPORT_PATTERNS:
        for match in pattern.finditer(text):
            module_names.update(_list_package_prefixes(match.group(1)))
    return module_names


def _list_dotted_prefixes(module: str) -> Iterator[str]:
    parts = [part for part in module.split(".") if part]
    for count in range(1, len(parts) + 1):
        yield ".".join(parts[:count])


def _list_package_prefixes(module: str) -> Iterator[str]:
    if module.startswith((".", "/")):
        return
    parts = [part for part in module.split("/") if part]
    first_count = 2 if module.startswith("@") else 1
    for count in range(first_count, len(parts) + 1):
        yield "/".join(parts[:count])
