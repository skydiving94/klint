"""What is known about a unit before it is read."""

from klint.core.models.unit_traits import UnitTraits


def test_no_language_is_known_by_default() -> None:
    assert UnitTraits().language is None
