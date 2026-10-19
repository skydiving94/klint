"""Where an audited unit sits in its source."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A source, such as a file or directory path, and an optional line span."""

    source: str
    start_line: int | None = None
    end_line: int | None = None

    @property
    def line_range(self) -> tuple[int, int] | None:
        """Return (start, end) when both lines are known."""
        if self.start_line is not None and self.end_line is not None:
            return (self.start_line, self.end_line)
        return None
