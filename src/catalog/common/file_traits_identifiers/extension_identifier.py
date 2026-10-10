from collections.abc import Mapping
from pathlib import Path

from src.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from src.core.models.file_traits import FileTraits


class ExtensionFileTraitsIdentifier(BaseFileTraitsIdentifier):
    """Identifies a file's traits from its extension, without opening the file.

    language_by_extension maps an extension with its leading dot, such as
    ".py", to a language name. Case is ignored.
    """

    def __init__(self, language_by_extension: Mapping[str, str]) -> None:
        self._language_by_extension = {
            extension.lower(): language
            for extension, language in language_by_extension.items()
        }

    def identify(self, path: str | Path) -> FileTraits:
        extension = Path(path).suffix.lower()
        return FileTraits(language=self._language_by_extension.get(extension))
