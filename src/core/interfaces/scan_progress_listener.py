from abc import ABC, abstractmethod
from pathlib import Path


class BaseScanProgressListener(ABC):
    """Told about each directory as the scan of an audit target goes."""

    @abstractmethod
    def report_directory_scanned(self, directory: Path) -> None:
        """Take note that ``directory`` has just been listed."""
