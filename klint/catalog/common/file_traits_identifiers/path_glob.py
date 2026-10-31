"""Matching a path against a glob such as "src/api/**" or "**/*.tsx"."""

import re
from functools import cache
from pathlib import PurePath


def does_path_match_glob(path: PurePath, glob: str) -> bool:
    """Return True when ``path``, a relative path, matches ``glob``.

    In a glob, "*" stands for any characters but "/", "?" for one such
    character, "**/" for any number of folders, none included, and a final
    "**" for anything beneath. Case counts.
    """
    return _compile_glob(glob).fullmatch(path.as_posix()) is not None


@cache
def _compile_glob(glob: str) -> re.Pattern[str]:
    pattern_parts: list[str] = []
    index = 0
    while index < len(glob):
        if glob.startswith("**/", index):
            pattern_parts.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            pattern_parts.append(".*")
            index += 2
        elif glob[index] == "*":
            pattern_parts.append("[^/]*")
            index += 1
        elif glob[index] == "?":
            pattern_parts.append("[^/]")
            index += 1
        else:
            pattern_parts.append(re.escape(glob[index]))
            index += 1
    return re.compile("".join(pattern_parts))
