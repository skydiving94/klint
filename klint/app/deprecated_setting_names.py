"""The old names of settings: each still works, with a warning, for one release."""

from collections.abc import Mapping

from klint.core.klint_warning import warn_about_deprecated_name

# Each old setting name, and the name that replaces it.
DEPRECATED_SETTING_NAME_TO_SETTING_NAME = {
    "KEV_MODE": "KLINT_JUDGE_MODE",
    "KEV_MODEL_NAME": "KLINT_JUDGE_MODEL",
    "KEV_BASE_URL": "KLINT_JUDGE_BASE_URL",
    "KEV_API_KEY": "KLINT_JUDGE_API_KEY",
}


def translate_deprecated_setting_names(
    key_to_value: Mapping[str, str], place: str
) -> dict[str, str]:
    """Return ``key_to_value`` with each old setting name replaced by its new one.

    Each old name found is reported as a KlintWarning that names ``place``,
    where it was set. When the new name is set as well, its value is kept.
    """
    translated = {
        key: value
        for key, value in key_to_value.items()
        if key not in DEPRECATED_SETTING_NAME_TO_SETTING_NAME
    }
    for key, value in key_to_value.items():
        new_key = DEPRECATED_SETTING_NAME_TO_SETTING_NAME.get(key)
        if new_key is None:
            continue
        warn_about_deprecated_name(key, new_key, place)
        translated.setdefault(new_key, value)
    return translated
