"""A value as JSON holds it."""

from collections.abc import Mapping, Sequence
from typing import TypeAlias

JsonValue: TypeAlias = (
    str | int | float | bool | Sequence["JsonValue"] | Mapping[str, "JsonValue"] | None
)
