"""Where a unit sits in its source."""

from src.core.models.location import Location


def test_location_line_range_needs_both_lines() -> None:
    assert Location("a.py", 1, 9).line_range == (1, 9)
    assert Location("a.py", 1).line_range is None
    assert Location("pkg").line_range is None
