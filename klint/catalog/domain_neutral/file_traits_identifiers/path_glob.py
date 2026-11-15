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
    return _compile_glob(glob, "/").fullmatch(path.as_posix()) is not None


def does_name_match_glob(qualified_name: str, glob: str) -> bool:
    """Return True when ``qualified_name``, such as "Cart.total", matches ``glob``.

    The glob is read as a path glob is, with "." in place of "/": "*"
    stands for any characters but ".", and "**" crosses them too.
    """
    return _compile_glob(glob, ".").fullmatch(qualified_name) is not None


@cache
def _compile_glob(glob: str, separator: str) -> re.Pattern[str]:
    any_folders = f"**{separator}"
    # "**/**/" means no more than "**/", and a run of them would make the
    # pattern slow to fail.
    while any_folders * 2 in glob:
        glob = glob.replace(any_folders * 2, any_folders)
    escaped_separator = re.escape(separator)
    pattern_parts: list[str] = []
    index = 0
    while index < len(glob):
        if glob.startswith(any_folders, index):
            pattern_parts.append(f"(?:.*{escaped_separator})?")
            index += 3
        elif glob.startswith("**", index):
            pattern_parts.append(".*")
            index += 2
        elif glob[index] == "*":
            pattern_parts.append(f"[^{escaped_separator}]*")
            index += 1
        elif glob[index] == "?":
            pattern_parts.append(f"[^{escaped_separator}]")
            index += 1
        else:
            pattern_parts.append(re.escape(glob[index]))
            index += 1
    return re.compile("".join(pattern_parts))
