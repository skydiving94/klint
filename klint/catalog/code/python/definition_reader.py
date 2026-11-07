"""Reads the classes and functions a parsed Python file defines into units."""

import ast
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from klint.catalog.code.python.definition_units import (
    AuditablePythonClassUnit,
    AuditablePythonDefinitionUnit,
    AuditablePythonFunctionUnit,
)
from klint.core.models.units import UnitTraits

DefinitionNode = ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
_DEFINITION_NODE_TYPES = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
# The nodes a definition can sit in without being nested in another one, as
# in the branches of an if statement or the handlers of a try statement.
_ENCLOSING_NODE_TYPES = (ast.stmt, ast.excepthandler, ast.match_case)


@dataclass(frozen=True)
class SourceFile:
    """A parsed Python file: its path, its traits, its lines and its tree.

    lines are numbered as the tree numbers them, the first at index 0.
    """

    path: str
    traits: UnitTraits
    lines: Sequence[str]
    tree: ast.Module


def read_definitions(
    source_file: SourceFile,
) -> tuple[AuditablePythonDefinitionUnit, ...]:
    """Return the units of the classes and functions at the top of ``source_file``.

    A unit is made for each class and function defined at the top of the
    file, and for each method and class defined in a class, at any depth;
    one in an if, try, with or loop statement counts as defined where that
    statement is. A function or class defined inside a function is part of
    that function's unit. Each unit's ID is the file's path and its
    qualified name, joined by "::"; when two units of the file share a
    qualified name, as a property and its setter do, each ID ends with ":"
    and its first line. The units come in file order.
    """
    qualified_name_counts = Counter(_list_qualified_names(source_file.tree, ""))
    return tuple(
        _build_unit(node, "", source_file, qualified_name_counts)
        for node in _find_definition_nodes(source_file.tree)
    )


def _build_unit(
    node: DefinitionNode,
    prefix: str,
    source_file: SourceFile,
    qualified_name_counts: Counter[str],
) -> AuditablePythonDefinitionUnit:
    """Return the unit of ``node``, whose qualified name starts with ``prefix``."""
    qualified_name = f"{prefix}{node.name}"
    start_line = min(
        [node.lineno, *(decorator.lineno for decorator in node.decorator_list)]
    )
    end_line = node.end_lineno or node.lineno
    unit_id = f"{source_file.path}::{qualified_name}"
    if qualified_name_counts[qualified_name] > 1:
        unit_id = f"{unit_id}:{start_line}"
    source = "\n".join(source_file.lines[start_line - 1 : end_line])
    if isinstance(node, ast.ClassDef):
        return AuditablePythonClassUnit(
            unit_id=unit_id,
            traits=source_file.traits,
            qualified_name=qualified_name,
            file_path=source_file.path,
            start_line=start_line,
            end_line=end_line,
            source=source,
            members=tuple(
                _build_unit(
                    member, f"{qualified_name}.", source_file, qualified_name_counts
                )
                for member in _find_definition_nodes(node)
            ),
        )
    return AuditablePythonFunctionUnit(
        unit_id=unit_id,
        traits=source_file.traits,
        qualified_name=qualified_name,
        file_path=source_file.path,
        start_line=start_line,
        end_line=end_line,
        source=source,
        body_start_line=_find_body_start_line(node, source_file.lines),
    )


def _find_definition_nodes(node: ast.AST) -> Iterator[DefinitionNode]:
    """Yield the classes and functions defined directly in ``node``, in order.

    Those in its compound statements count, and those inside the classes
    and functions found do not.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _DEFINITION_NODE_TYPES):
            yield child
        elif isinstance(child, _ENCLOSING_NODE_TYPES):
            yield from _find_definition_nodes(child)


def _list_qualified_names(node: ast.AST, prefix: str) -> Iterator[str]:
    """Yield the qualified name of each class and function that becomes a unit."""
    for definition in _find_definition_nodes(node):
        qualified_name = f"{prefix}{definition.name}"
        yield qualified_name
        if isinstance(definition, ast.ClassDef):
            yield from _list_qualified_names(definition, f"{qualified_name}.")


def _find_body_start_line(
    node: ast.FunctionDef | ast.AsyncFunctionDef, lines: Sequence[str]
) -> int | None:
    """Return the first line of the function's body after its docstring.

    None when the body is the docstring alone, or when that line also holds
    the end of the signature, as in a function written on one line.
    """
    body = node.body
    if not _is_docstring(body[0]):
        first_statement = body[0]
    elif len(body) > 1:
        first_statement = body[1]
    else:
        return None
    if (
        isinstance(first_statement, _DEFINITION_NODE_TYPES)
        and first_statement.decorator_list
    ):
        # A decorated definition starts a line of its own, at its first
        # decorator.
        return min(decorator.lineno for decorator in first_statement.decorator_list)
    line = lines[first_statement.lineno - 1]
    # col_offset counts bytes; a line that starts with the statement has
    # only spaces or tabs before it, and those are one byte each.
    if line[: first_statement.col_offset].strip():
        return None
    return first_statement.lineno


def _is_docstring(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and isinstance(statement.value.value, str)
    )
