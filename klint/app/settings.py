import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from klint.app.judge_mode import JudgeMode
from klint.app.project_config import (
    KNOWN_SETTING_NAMES,
    find_project_config,
    read_project_config,
    warn_about_settings_in_rules_file,
)
from klint.core.models.file_traits_override import FileTraitsOverride

# The model and the server address the judge uses unless a setting names others.
_DEFAULT_MODEL_NAME = "jaredpalmer/kev-4b"
_DEFAULT_BASE_URL = "http://127.0.0.1:8009"
# Built-in rule packs, relative to klint/resources/catalog/ and merged in this
# order. Each pack states in its header the files it loads for.
_BUILT_IN_RULE_PACKS = (
    "code/common/backend.json",
    "code/typescript/react.json",
    "code/common/structure.json",
    "code/python/project_structure.json",
)
# The packs a file whose language is not identified is asked, unless the
# config file names its own.
_BUILT_IN_FALLBACK_RULE_PACKS = (
    "code/common/backend.json",
    "code/common/structure.json",
)
# The built-in list of languages and their file extensions, relative to
# klint/resources/catalog/.
_BUILT_IN_LANGUAGE_TO_FILE_EXTENSIONS = "code/common/language_to_file_extensions.json"
# The built-in tables that tell which side of a project a file belongs to,
# relative to klint/resources/catalog/.
_BUILT_IN_TAG_DETECTION = "code/common/tag_detection.json"


@dataclass(frozen=True)
class _SettingSource:
    """One place settings are read from.

    description names it in messages, and key_to_value holds the settings
    it sets. A relative path it sets is taken from base_folder.
    """

    description: str
    key_to_value: Mapping[str, str]
    base_folder: Path


@dataclass(frozen=True)
class _SettingValue:
    """The value a setting takes, and the source that set it."""

    value: str
    source: _SettingSource


def _find_setting(key: str, sources: Sequence[_SettingSource]) -> _SettingValue | None:
    """Return the value of ``key`` from the first source that sets it.

    An empty value counts as not set. None when no source sets it.
    """
    for source in sources:
        value = source.key_to_value.get(key)
        if value:
            return _SettingValue(value=value, source=source)
    return None


def _read_judge_mode(setting: _SettingValue | None) -> JudgeMode:
    """Return the judge mode ``setting`` names, in any case; LOCAL when unset.

    Raises ValueError listing the valid values when it names none.
    """
    if setting is None:
        return JudgeMode.LOCAL
    try:
        return JudgeMode(setting.value.lower())
    except ValueError:
        raise ValueError(
            f"KEV_MODE {setting.value!r} set in {setting.source.description} "
            f"is not a judge mode; valid values: {[mode.value for mode in JudgeMode]}"
        ) from None


def _locate_built_in_resource(relative_path: str) -> Path:
    """Locate a built-in data file inside the installed package."""
    catalog = resources.files("klint.resources") / "catalog"
    return Path(str(catalog / relative_path))


def _built_in_packs(relative_paths: Sequence[str]) -> tuple[Path, ...]:
    """Locate built-in rule packs inside the installed package."""
    return tuple(_locate_built_in_resource(relative) for relative in relative_paths)


def _locate_built_in_rule_packs() -> tuple[Path, ...]:
    return _built_in_packs(_BUILT_IN_RULE_PACKS)


def _locate_built_in_fallback_rule_packs() -> tuple[Path, ...]:
    return _built_in_packs(_BUILT_IN_FALLBACK_RULE_PACKS)


def _locate_built_in_language_to_file_extensions() -> Path:
    """Locate the built-in list of languages and their file extensions."""
    return _locate_built_in_resource(_BUILT_IN_LANGUAGE_TO_FILE_EXTENSIONS)


def _locate_built_in_tag_detection() -> Path:
    """Locate the built-in tag detection tables."""
    return _locate_built_in_resource(_BUILT_IN_TAG_DETECTION)


def _resolve_setting_path(setting: _SettingValue | None) -> Path | None:
    """Return the path ``setting`` names; a relative one is taken from its source."""
    if setting is None:
        return None
    return (setting.source.base_folder / setting.value).resolve()


@dataclass(frozen=True)
class AppSettings:
    model_name: str
    kev_mode: JudgeMode = JudgeMode.LOCAL
    kev_base_url: str = _DEFAULT_BASE_URL
    kev_api_key: str | None = None
    # The packs chosen by the traits of each file, and the packs a file whose
    # language is not identified is asked instead.
    built_in_rule_packs: tuple[Path, ...] = field(
        default_factory=_locate_built_in_rule_packs
    )
    fallback_rule_packs: tuple[Path, ...] = field(
        default_factory=_locate_built_in_fallback_rule_packs
    )
    # A file that replaces every built-in pack for one command, klint or
    # klint-project; its rules are then asked about every file.
    file_contents_rule_pack_override: Path | None = None
    project_structure_rule_pack_override: Path | None = None
    # The project's klint.json, and the files whose rules merge over the
    # loaded packs for every file: the klint.json when it holds rules.
    discovered_config_path: Path | None = None
    project_rule_packs: tuple[Path, ...] = ()
    # The file that lists each language's file extensions.
    language_to_file_extensions_path: Path = field(
        default_factory=_locate_built_in_language_to_file_extensions
    )
    # The file of tables that tell which side of a project a file belongs to.
    tag_detection_path: Path = field(default_factory=_locate_built_in_tag_detection)
    # What the project's klint.json says about some files, over what is
    # detected; the first entry whose glob matches a file decides.
    file_traits_overrides: tuple[FileTraitsOverride, ...] = ()

    @classmethod
    def from_env(
        cls,
        target_path: Path | None = None,
        rules_path: Path | None = None,
    ) -> "AppSettings":
        """Load the settings for an audit of ``target_path``.

        Each setting is taken from the first of these that sets it: the
        shell's environment variables, the "env" block of the project's
        klint.json, the built-in default. A relative path is taken from the
        working directory when the shell sets it, and from the folder of the
        klint.json when the file does. ``rules_path``, the file given with
        --rules, holds rules only: a setting in it is ignored with a warning.
        Nothing outside the returned value is changed.
        """
        config_path = find_project_config(target_path)
        config = None if config_path is None else read_project_config(config_path)
        if rules_path is not None and (
            config_path is None or rules_path.resolve() != config_path.resolve()
        ):
            warn_about_settings_in_rules_file(rules_path)
        sources = [
            _SettingSource(
                description="the environment",
                key_to_value={
                    key: os.environ[key]
                    for key in KNOWN_SETTING_NAMES
                    if key in os.environ
                },
                base_folder=Path.cwd(),
            )
        ]
        if config is not None:
            sources.append(
                _SettingSource(
                    description=f"'{config.path}'",
                    key_to_value=config.setting_name_to_value,
                    base_folder=config.path.parent,
                )
            )

        def _get_setting(key: str) -> str | None:
            setting = _find_setting(key, sources)
            return None if setting is None else setting.value

        return cls(
            model_name=_get_setting("KEV_MODEL_NAME") or _DEFAULT_MODEL_NAME,
            kev_mode=_read_judge_mode(_find_setting("KEV_MODE", sources)),
            kev_base_url=_get_setting("KEV_BASE_URL") or _DEFAULT_BASE_URL,
            kev_api_key=_get_setting("KEV_API_KEY"),
            fallback_rule_packs=(
                _locate_built_in_fallback_rule_packs()
                if config is None or config.fallback_rule_packs is None
                else config.fallback_rule_packs
            ),
            # When set, each variable names one file that replaces the
            # built-in packs for its command.
            file_contents_rule_pack_override=_resolve_setting_path(
                _find_setting("KEV_DEFAULT_RULES_PATH", sources)
            ),
            project_structure_rule_pack_override=_resolve_setting_path(
                _find_setting("KEV_DEFAULT_PROJECT_RULES_PATH", sources)
            ),
            discovered_config_path=config_path,
            project_rule_packs=(
                (config.path,) if config is not None and config.does_hold_rules else ()
            ),
            file_traits_overrides=(
                () if config is None else config.file_traits_overrides
            ),
        )
