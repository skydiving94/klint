"""Keeping what the judge reads within a number of characters."""

from collections.abc import Sequence


def join_lines_within_budget(
    lines: Sequence[str],
    character_budget: int,
    what_lines_describe: str,
    stated_budget: int | None = None,
) -> str:
    """Join ``lines`` into a text of at most ``character_budget`` characters.

    When they do not all fit, the leading lines that fit are kept and a
    last line says how many lines of ``what_lines_describe``, such as "the
    file", were left out. A first line too long to fit is cut, and the last
    line says so too. The last line names ``stated_budget`` as the budget
    kept to, ``character_budget`` unless given: the budget of a longer text
    the lines are part of.
    """
    text = "\n".join(lines)
    if len(text) <= character_budget:
        return text
    named_budget = character_budget if stated_budget is None else stated_budget
    # The longest last line there can be: every line left out.
    longest_trimming_line = _format_trimming_line(
        len(lines), what_lines_describe, named_budget, is_first_line_cut=True
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
            named_budget,
            is_first_line_cut=True,
        )
        return f"{first_line_part}\n{trimming_line}"[:character_budget]
    trimming_line = _format_trimming_line(
        len(lines) - kept_count,
        what_lines_describe,
        named_budget,
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
    left_out_parts: list[str] = []
    if is_first_line_cut:
        left_out_parts.append("the rest of the line above")
    if left_out_count > 0:
        line_word = "line" if left_out_count == 1 else "lines"
        left_out_parts.append(
            f"{left_out_count} more {line_word} of {what_lines_describe}"
        )
    return (
        f"[... {' and '.join(left_out_parts)} left out to stay within "
        f"{character_budget} characters]"
    )
