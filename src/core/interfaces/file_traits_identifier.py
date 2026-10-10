from abc import ABC, abstractmethod
from pathlib import Path

from src.core.models.file_traits import FileTraits


class BaseFileTraitsIdentifier(ABC):
    @abstractmethod
    def identify(self, path: str | Path) -> FileTraits:
        """Return what can be told about the file at ``path`` before it is read."""
        pass
