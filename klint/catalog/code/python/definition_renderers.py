"""What the judge reads about a Python class or function."""

import textwrap
from collections.abc import Iterator

from klint.catalog.code.python.definition_units import (
    AuditablePythonClassUnit,
    AuditablePythonFunctionUnit,
)
from klint.catalog.domain_neutral import join_lines_within_budget
from klint.core.interfaces import BaseUnitRenderer
from klint.core.models.audits import RenderInput


class PythonFunctionRenderer(BaseUnitRenderer):
    """Shows the judge a function's source, decorators included, unindented.

    A function over the character budget is shown from its first line, as
    far as the budget goes.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        function = render_input.get_unit_as(AuditablePythonFunctionUnit)
        return _fit_within_budget(
            textwrap.dedent(function.source),
            render_input.character_budget,
            "the function",
        )


class PythonClassRenderer(BaseUnitRenderer):
    """Shows the judge a class, unindented, with the body of each method left out.

    Each method is judged on its own, so the class shows what it is made
    of: its decorators, bases, docstring and class-level statements, and
    each method's signature and docstring, its body replaced by "...". The
    methods of a class defined in it are shown the same way. A class over
    the character budget is shown from its first line, as far as the
    budget goes.
    """

    def render_subject(self, render_input: RenderInput) -> str:
        class_unit = render_input.get_unit_as(AuditablePythonClassUnit)
        return _fit_within_budget(
            textwrap.dedent(_outline_class(class_unit)),
            render_input.character_budget,
            "the class",
        )


def _outline_class(class_unit: AuditablePythonClassUnit) -> str:
    """Return the source of ``class_unit`` with each method's body left out."""
    lines = class_unit.source.split("\n")
    first_line = class_unit.start_line
    outline: list[str] = []
    next_line = first_line
    for method in sorted(
        _list_methods_beneath(class_unit), key=lambda method: method.start_line
    ):
        if method.body_start_line is None:
            continue
        body_index = method.body_start_line - first_line
        outline.extend(lines[next_line - first_line : body_index])
        body_line = lines[body_index]
        indentation = body_line[: len(body_line) - len(body_line.lstrip())]
        outline.append(f"{indentation}...")
        next_line = method.end_line + 1
    outline.extend(lines[next_line - first_line :])
    return "\n".join(outline)


def _list_methods_beneath(
    class_unit: AuditablePythonClassUnit,
) -> Iterator[AuditablePythonFunctionUnit]:
    """Yield the methods of ``class_unit`` and of the classes defined in it."""
    for member in class_unit.members:
        if isinstance(member, AuditablePythonFunctionUnit):
            yield member
        elif isinstance(member, AuditablePythonClassUnit):
            yield from _list_methods_beneath(member)


def _fit_within_budget(text: str, character_budget: int, what_text_is: str) -> str:
    """Return ``text``, from its first line as far as the budget goes."""
    if len(text) <= character_budget:
        return text
    return join_lines_within_budget(text.split("\n"), character_budget, what_text_is)
