"""Keeping what the judge reads within a number of characters."""

from collections.abc import Sequence


def join_lines_within_budget(
    lines: Sequence[str], character_budget: int, what_lines_describe: str
) -> str:
    """Join ``lines`` into a text of at most ``character_budget`` characters.

    When they do not all fit, the leading lines that fit are kept and a
    last line says how many lines of ``what_lines_describe``, such as "the
    file", were left out. A first line too long to fit is cut, and the last
    line says so too.
    """
    text = "\n".join(lines)
    if len(text) <= character_budget:
        return text
    # The longest last line there can be: every line left out.
    longest_trimming_line = _format_trimming_line(
        len(lines), what_lines_describe, character_budget, is_first_line_cut=True
    )
    room = character_budget - len(longest_trimming_line)
    kept_length = 0
    kept_count = 0
    for line in lines:
        # Each kept line takes its length and the line break after it.
        if kept_length + len(line) + 1 > room:
            break
        kept_length += len(line) + 1
        kept_count += 1
    if kept_count == 0:
        first_line_part = lines[0][: max(room - 1, 0)]
        trimming_line = _format_trimming_line(
            len(lines) - 1,
            what_lines_describe,
            character_budget,
            is_first_line_cut=True,
        )
        return f"{first_line_part}\n{trimming_line}"[:character_budget]
    trimming_line = _format_trimming_line(
        len(lines) - kept_count,
        what_lines_describe,
        character_budget,
        is_first_line_cut=False,
    )
    return "\n".join([*lines[:kept_count], trimming_line])[:character_budget]


def _format_trimming_line(
    left_out_count: int,
    what_lines_describe: str,
    character_budget: int,
    is_first_line_cut: bool,
) -> str:
    """Return the last line of a trimmed text, saying what it left out."""
    cut_part = "the rest of the line above and " if is_first_line_cut else ""
    return (
        f"[... {cut_part}{left_out_count} more lines of {what_lines_describe} "
        f"left out to stay within {character_budget} characters]"
    )
