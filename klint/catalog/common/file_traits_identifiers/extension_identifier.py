from collections.abc import Mapping
from pathlib import Path

from klint.core.interfaces.file_traits_identifier import BaseFileTraitsIdentifier
from klint.core.models.unit_traits import UnitTraits


class ExtensionFileTraitsIdentifier(BaseFileTraitsIdentifier):
    """Identifies a file's traits from its extension, without opening the file.

    file_extension_to_language maps an extension with its leading dot, such as
    ".py", to a language name. Case is ignored.
    """

    def __init__(self, file_extension_to_language: Mapping[str, str]) -> None:
        self._file_extension_to_language = {
            extension.lower(): language
            for extension, language in file_extension_to_language.items()
        }

    def identify(self, path: str | Path, scan_root: Path | None = None) -> UnitTraits:
        del scan_root
        extension = Path(path).suffix.lower()
        return UnitTraits(language=self._file_extension_to_language.get(extension))
