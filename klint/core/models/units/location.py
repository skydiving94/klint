"""Where an audited unit sits: a path, and the lines it spans."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """A path, such as that of a file or directory, and an optional line span."""

    path: str
    start_line: int | None = None
    end_line: int | None = None

    @property
    def line_range(self) -> tuple[int, int] | None:
        """Return (start, end) when both lines are known."""
        if self.start_line is not None and self.end_line is not None:
            return (self.start_line, self.end_line)
        return None
