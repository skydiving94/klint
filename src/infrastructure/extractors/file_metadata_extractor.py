import ast
from pathlib import Path
from typing import List

from src.core.domain.units import AuditableFileMetadataUnit
from src.core.interfaces.extractor import BaseFileMetadataExtractor


class PythonFileMetadataExtractor(BaseFileMetadataExtractor):
    """Extracts line count, exports, imports, classes, and functions from Python files."""

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() == ".py"

    def extract_file(self, path: Path) -> AuditableFileMetadataUnit:
        source = path.read_text(encoding="utf-8", errors="replace")
        line_count = len(source.splitlines())
        imports: List[str] = []
        exports: List[str] = []
        classes: List[str] = []
        functions: List[str] = []

        try:
            tree = ast.parse(source, filename=str(path))
            for node in tree.body:
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    imports.append(module)
                    if path.name == "__init__.py":
                        exports.extend(
                            alias.asname or alias.name for alias in node.names)
                elif isinstance(node, ast.Assign):
                    exports.extend(self._extract_dunder_all(node))
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)
        except SyntaxError:
            pass

        return AuditableFileMetadataUnit(
            unit_id=str(path),
            file_name=path.name,
            file_path=str(path),
            line_count=line_count,
            imports=imports,
            exports=sorted(set(exports)),
            classes=classes,
            functions=functions,
        )

    def _extract_dunder_all(self, node: ast.Assign) -> List[str]:
        if not any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            return []
        if isinstance(node.value, (ast.List, ast.Tuple)):
            return [
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            ]
        return []


class FallbackFileMetadataExtractor(BaseFileMetadataExtractor):
    """Fallback extractor that records basic file identity and line count."""

    def supports(self, path: Path) -> bool:
        return True

    def extract_file(self, path: Path) -> AuditableFileMetadataUnit:
        content = path.read_text(encoding="utf-8", errors="replace")
        return AuditableFileMetadataUnit(
            unit_id=str(path),
            file_name=path.name,
            file_path=str(path),
            line_count=len(content.splitlines()),
        )
