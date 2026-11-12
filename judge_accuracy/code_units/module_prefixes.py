"""Shorter modules cut from a case module, to have units of every length.

A prefix ends after a top-level statement, or after a statement of the body
of a top-level function, which it then ends with. Either way it is a valid
module whose every unit is true when the whole module's are. The prefixes
chosen give a file of each band of length, and, for each top-level
function, a version of it of each band its body reaches.
"""

import ast
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from judge_accuracy.code_units.length_bands import LENGTH_BANDS, LengthBand

_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


@dataclass(frozen=True)
class _CutLine:
    """A line a prefix may end on, and the lengths of what the prefix holds.

    function_length is the length of the top-level function the prefix
    ends inside or with; None when it ends with another statement.
    """

    end_line: int
    file_length: int
    function_start_line: int | None
    function_length: int | None


def cut_to_line(source: str, end_line: int) -> str:
    """Return the lines of ``source`` up to ``end_line``, ending in a line break."""
    lines = source.splitlines(keepends=True)
    return "".join(lines[:end_line]).rstrip("\n") + "\n"


def choose_prefix_end_lines(
    source: str, bands: Sequence[LengthBand] = LENGTH_BANDS
) -> list[int]:
    """Return the lines the prefixes of ``source`` to judge end on, in order.

    That is the whole module; for each band of length, the longest prefix
    in it; and for each top-level function and each band, the longest
    prefix that ends inside or with the function and cuts it to that band.
    """
    cut_lines = _list_cut_lines(source)
    chosen = {cut_lines[-1].end_line}
    function_start_lines = {
        cut.function_start_line
        for cut in cut_lines
        if cut.function_start_line is not None
    }
    for band in bands:
        chosen.update(
            _find_longest(
                cut.end_line for cut in cut_lines if band.does_hold(cut.file_length)
            )
        )
        for start_line in function_start_lines:
            chosen.update(
                _find_longest(
                    cut.end_line
                    for cut in cut_lines
                    if cut.function_start_line == start_line
                    and cut.function_length is not None
                    and band.does_hold(cut.function_length)
                )
            )
    return sorted(chosen)


def _list_cut_lines(source: str) -> list[_CutLine]:
    """Return each line a prefix of ``source`` may end on, in order.

    That is the last line of each top-level statement, and of each statement
    of a top-level function's body after its first.
    """
    lines = source.splitlines(keepends=True)
    cut_lines: dict[int, _CutLine] = {}
    for statement in ast.parse(source).body:
        end_lines = [statement.end_lineno or statement.lineno]
        start_line: int | None = None
        if isinstance(statement, _FUNCTION_NODES):
            start_line = min(
                [statement.lineno]
                + [decorator.lineno for decorator in statement.decorator_list]
            )
            end_lines += [
                body_statement.end_lineno or body_statement.lineno
                for body_statement in statement.body[1:]
            ]
        for end_line in end_lines:
            cut_lines[end_line] = _CutLine(
                end_line=end_line,
                file_length=len(cut_to_line(source, end_line)),
                function_start_line=start_line,
                function_length=(
                    None
                    if start_line is None
                    else len("".join(lines[start_line - 1 : end_line]).rstrip("\n"))
                ),
            )
    return [cut_lines[end_line] for end_line in sorted(cut_lines)]


def _find_longest(end_lines: Iterable[int]) -> list[int]:
    """Return the last of ``end_lines`` in a list; an empty list when none."""
    collected = list(end_lines)
    return [max(collected)] if collected else []
