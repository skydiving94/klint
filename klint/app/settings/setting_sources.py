"""The places settings are read from, and how each setting's value is read."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from klint.app.answer_cache_folder import read_answer_cache_folder
from klint.app.commit_threshold import read_commit_min_confidence
from klint.app.judge_mode import JudgeMode
from klint.app.project_config import KNOWN_SETTING_NAMES, ProjectConfig
from klint.app.removed_setting_names import warn_about_removed_setting_names


@dataclass(frozen=True)
class SettingSource:
    """One place settings are read from.

    description names it in messages, and key_to_value holds the settings
    it sets. A relative path it sets is taken from base_folder.
    """

    description: str
    key_to_value: Mapping[str, str]
    base_folder: Path


@dataclass(frozen=True)
class SettingValue:
    """The value a setting takes, and the source that set it."""

    value: str
    source: SettingSource


def read_environment_source() -> SettingSource:
    """Return the settings the shell's environment variables set.

    A removed setting name is ignored, with a warning naming its replacement.
    """
    warn_about_removed_setting_names(os.environ, "in the environment")
    return SettingSource(
        description="the environment",
        key_to_value={
            key: os.environ[key] for key in KNOWN_SETTING_NAMES if key in os.environ
        },
        base_folder=Path.cwd(),
    )


def read_config_source(config: ProjectConfig) -> SettingSource:
    """Return the settings the "env" block of the klint.json ``config`` sets."""
    return SettingSource(
        description=f"'{config.path}'",
        key_to_value=config.setting_name_to_value,
        base_folder=config.path.parent,
    )


def find_setting(key: str, sources: Sequence[SettingSource]) -> SettingValue | None:
    """Return the value of ``key`` from the first source that sets it.

    An empty value counts as not set. None when no source sets it.
    """
    for source in sources:
        value = source.key_to_value.get(key)
        if value:
            return SettingValue(value=value, source=source)
    return None


def read_judge_mode(setting: SettingValue | None) -> JudgeMode:
    """Return the judge mode ``setting`` names, in any case; LOCAL when unset.

    Raises ValueError listing the valid values when it names none.
    """
    if setting is None:
        return JudgeMode.LOCAL
    try:
        return JudgeMode(setting.value.lower())
    except ValueError:
        raise ValueError(
            f"KLINT_JUDGE_MODE {setting.value!r} set in {setting.source.description} "
            f"is not a judge mode; valid values: {[mode.value for mode in JudgeMode]}"
        ) from None


def read_answer_cache_setting(setting: SettingValue | None) -> Path | None:
    """Return the answer cache folder ``setting`` chooses; the default when unset."""
    if setting is None:
        return read_answer_cache_folder(None, Path.cwd())
    return read_answer_cache_folder(setting.value, setting.source.base_folder)


def read_commit_min_confidence_setting(setting: SettingValue | None) -> float | None:
    """Return the commit threshold ``setting`` gives; None when unset."""
    if setting is None:
        return None
    return read_commit_min_confidence(setting.value, setting.source.description)


def resolve_setting_path(setting: SettingValue | None) -> Path | None:
    """Return the path ``setting`` names; a relative one is taken from its source."""
    if setting is None:
        return None
    return (setting.source.base_folder / setting.value).resolve()
