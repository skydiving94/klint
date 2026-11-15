"""Where the answer cache lives unless a setting moves or turns it off."""

import os
import sys
from pathlib import Path

# The value of KLINT_ANSWER_CACHE that turns the cache off.
ANSWER_CACHE_OFF = "off"
_CACHE_FOLDER_NAME = "klint"
_ANSWERS_FOLDER_NAME = "answers"


def locate_default_answer_cache_folder() -> Path:
    """Return the answer cache's folder in the user's cache directory.

    The cache directory is the platform's: ~/Library/Caches on macOS,
    %LOCALAPPDATA% on Windows, and $XDG_CACHE_HOME or ~/.cache elsewhere.
    """
    if sys.platform == "darwin":
        cache_root = Path.home() / "Library" / "Caches"
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        cache_root = (
            Path(local_app_data)
            if local_app_data
            else Path.home() / "AppData" / "Local"
        )
    else:
        xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
        cache_root = Path(xdg_cache_home) if xdg_cache_home else Path.home() / ".cache"
    return cache_root / _CACHE_FOLDER_NAME / _ANSWERS_FOLDER_NAME


def read_answer_cache_folder(value: str | None, base_folder: Path) -> Path | None:
    """Return the folder the KLINT_ANSWER_CACHE value ``value`` names.

    The default folder when ``value`` is not set, None when it is "off" in
    any case, else the folder it names; a relative one is taken from
    ``base_folder``.
    """
    if value is None:
        return locate_default_answer_cache_folder()
    if value.strip().lower() == ANSWER_CACHE_OFF:
        return None
    return (base_folder / value).resolve()
