"""Reads a JSON file that holds one object, naming the file when it cannot."""

import json
from pathlib import Path


def read_json_object_file(
    path: Path, file_description: str, expected_object: str
) -> dict[object, object]:
    """Return the JSON object in ``path``.

    ``file_description`` names the kind of file in each error, such as
    "Tag detection file", and ``expected_object`` says what the object must
    hold. Raises FileNotFoundError when the file is missing, and ValueError
    naming the file when it is not valid JSON or does not hold an object.
    """
    if not path.is_file():
        raise FileNotFoundError(f"{file_description} does not exist: {path}")
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(
            f"{file_description} '{path}' is not valid JSON: {error}"
        ) from error
    if not isinstance(raw, dict):
        raise ValueError(f"{file_description} '{path}' must be {expected_object}")
    return raw
