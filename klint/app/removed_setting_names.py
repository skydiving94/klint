"""The old names of settings, which klint no longer reads."""

from collections.abc import Iterable

from klint.core import warn_about_removed_name

# Each removed setting name, and the name that replaces it.
REMOVED_SETTING_NAME_TO_SETTING_NAME = {
    "KEV_MODE": "KLINT_JUDGE_MODE",
    "KEV_MODEL_NAME": "KLINT_JUDGE_MODEL",
    "KEV_BASE_URL": "KLINT_JUDGE_BASE_URL",
    "KEV_API_KEY": "KLINT_JUDGE_API_KEY",
    "KEV_DEFAULT_RULES_PATH": "KLINT_REPLACE_FILE_RULES",
    "KEV_DEFAULT_PROJECT_RULES_PATH": "KLINT_REPLACE_PROJECT_RULES",
}


def warn_about_removed_setting_names(keys: Iterable[str], place: str) -> None:
    """Warn about each removed setting name among ``keys``, naming its replacement.

    ``place`` says where the keys were set. A removed name is ignored.
    """
    for key in sorted(keys):
        new_key = REMOVED_SETTING_NAME_TO_SETTING_NAME.get(key)
        if new_key is not None:
            warn_about_removed_name(key, new_key, place)
