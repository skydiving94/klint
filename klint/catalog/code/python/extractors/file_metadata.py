import ast
from pathlib import Path

from klint.catalog.code.common.extractors.file_metadata_base import (
    BaseFileMetadataExtractor,
)
from klint.catalog.code.common.units.file_metadata import AuditableFileMetadataUnit
from klint.core.klint_warning import warn_about_unparseable_file
from klint.core.models.file_traits import FileTraits


class PythonFileMetadataExtractor(BaseFileMetadataExtractor):
    """Extracts a Python file's line count, exports, imports, classes and functions.

    A file the parser gives up on is marked unparseable, with a warning, and
    keeps only its line count.
    """

    def extract_file(self, path: Path, traits: FileTraits) -> AuditableFileMetadataUnit:
        source = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(source.splitlines())
        imports: list[str] = []
        exports: list[str] = []
        classes: list[str] = []
        functions: list[str] = []
        is_unparseable = False

        try:
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, MemoryError, RecursionError) as error:
            # The parser reports source nested too deeply for it as a
            # MemoryError or a RecursionError rather than a SyntaxError.
            warn_about_unparseable_file(path, error)
            is_unparseable = True
        else:
            # Top-level declarations (exports, classes, functions)
            for stmt in tree.body:
                if isinstance(stmt, ast.ImportFrom) and path.name == "__init__.py":
                    exports.extend(alias.asname or alias.name for alias in stmt.names)
                elif isinstance(stmt, ast.Assign):
                    exports.extend(self._extract_dunder_all(stmt))
                elif isinstance(stmt, ast.ClassDef):
                    classes.append(stmt.name)
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(stmt.name)

            # Walk the full AST for imports, both top-level and lazy function imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in imports:
                            imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    prefix = "." * node.level
                    module = prefix + (node.module or "")
                    if module and module not in imports:
                        imports.append(module)
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        if not node.module:
                            rel_target = f"{prefix}{alias.name}"
                            if rel_target not in imports:
                                imports.append(rel_target)
                        elif alias.name.islower():
                            sub_target = f"{module}.{alias.name}"
                            if sub_target not in imports:
                                imports.append(sub_target)

        return AuditableFileMetadataUnit(
            unit_id=str(path),
            language=traits.language,
            file_name=path.name,
            file_path=str(path),
            line_count=line_count,
            imports=imports,
            exports=sorted(set(exports)),
            classes=classes,
            functions=functions,
            is_unparseable=is_unparseable,
        )

    def _extract_dunder_all(self, node: ast.Assign) -> list[str]:
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            return []
        if isinstance(node.value, (ast.List, ast.Tuple)):
            return [
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
        return []
