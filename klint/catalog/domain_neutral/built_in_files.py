"""Where the data files that come with klint are."""

from importlib import resources
from pathlib import Path


def locate_built_in_catalog_file(relative_path: str) -> Path:
    """Return the path of the data file at ``relative_path`` in the catalog.

    The catalog's data files are under klint/resources/catalog/ in the
    installed package.
    """
    catalog = resources.files("klint.resources") / "catalog"
    return Path(str(catalog / relative_path))
