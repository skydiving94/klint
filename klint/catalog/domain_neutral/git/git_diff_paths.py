"""Reads the paths in git's diff headers: quoted or not, with a prefix or not."""

# The escapes git uses in a quoted path, other than three octal digits.
_ESCAPE_TO_BYTE = {
    "a": 0x07,
    "b": 0x08,
    "t": 0x09,
    "n": 0x0A,
    "v": 0x0B,
    "f": 0x0C,
    "r": 0x0D,
    '"': 0x22,
    "\\": 0x5C,
}


def find_path_of_unrenamed_file(paths_text: str) -> str | None:
    """Return the path in "<old> <new>", a file's two paths when it keeps its name.

    The two paths are the same but for a prefix of one folder each, such as
    "a/" and "b/", or the same with no prefix, as ``--no-prefix`` writes
    them. Returns None when they are not.
    """
    if paths_text.startswith('"'):
        source_path, rest = read_quoted_text(paths_text)
        destination_path = unquote_path(rest.removeprefix(" "))
    else:
        half_length = (len(paths_text) - 1) // 2
        source_path = paths_text[:half_length]
        destination_path = paths_text[half_length + 1 :]
    if source_path == destination_path:
        return destination_path
    source_parts = source_path.split("/", 1)
    destination_parts = destination_path.split("/", 1)
    if (
        len(source_parts) == 2
        and len(destination_parts) == 2
        and source_parts[1] == destination_parts[1]
    ):
        return destination_parts[1]
    return None


def unquote_path(text: str) -> str:
    """Return the path ``text`` holds, quoted as git quotes an unusual path or not.

    Raises ValueError when a quoted path is not quoted as git quotes one.
    """
    if not text.startswith('"'):
        return text
    path, rest = read_quoted_text(text)
    if rest:
        raise ValueError(f"the quoted path {text} is followed by '{rest}'")
    return path


def read_quoted_text(text: str) -> tuple[str, str]:
    """Return the text quoted at the start of ``text``, unescaped, and what follows.

    The quoted text is read as git writes it: C escapes, and any other byte
    as three octal digits. Raises ValueError when it is not.
    """
    path_bytes = bytearray()
    index = 1
    while index < len(text):
        character = text[index]
        if character == '"':
            return path_bytes.decode("utf-8", errors="replace"), text[index + 1 :]
        if character != "\\":
            path_bytes.extend(character.encode("utf-8"))
            index += 1
            continue
        escape = text[index + 1 : index + 2]
        if escape in _ESCAPE_TO_BYTE:
            path_bytes.append(_ESCAPE_TO_BYTE[escape])
            index += 2
        elif text[index + 1 : index + 4].isdigit():
            path_bytes.append(int(text[index + 1 : index + 4], 8))
            index += 4
        else:
            raise ValueError(f"the quoted path {text} has an unknown escape")
    raise ValueError(f"the quoted path {text} has no closing quote")
