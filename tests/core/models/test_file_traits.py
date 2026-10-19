"""What is known about a file before it is read."""

from klint.core.models.file_traits import FileTraits


def test_no_language_is_known_by_default() -> None:
    assert FileTraits().language is None
