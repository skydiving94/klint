import json
import os
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from klint.app.judge_mode import JudgeMode
from klint.core.klint_warning import KlintWarning

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
CONFIG_FILENAMES = ("klint.json", ".klintrc.json", ".klintrc")
# The key of a config file that replaces the built-in fallback packs.
_FALLBACK_RULE_PACKS_KEY = "fallback_rule_packs"
# The settings that the "env" block of a config file may set.
_KNOWN_ENV_KEYS = frozenset(
    {
        "KEV_MODEL_NAME",
        "KEV_DEFAULT_RULES_PATH",
        "KEV_DEFAULT_PROJECT_RULES_PATH",
        "KEV_MODE",
        "KEV_BASE_URL",
        "KEV_API_KEY",
    }
)


def find_project_config(start_path: Path | None = None) -> Path | None:
    """Search target directory (or cwd) for a klint.json / .klintrc.json file."""
    search_dir = (start_path or Path.cwd()).resolve()
    if search_dir.is_file():
        search_dir = search_dir.parent
    for directory in (search_dir, Path.cwd().resolve()):
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _read_config(config_path: Path | None) -> dict[str, object]:
    """Return the content of the config file; empty when there is none.

    Raises ValueError naming the file when it cannot be read as a JSON
    object.
    """
    if config_path is None or not config_path.is_file():
        return {}
    try:
        raw: object = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"'{config_path}' is not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"'{config_path}' must be a JSON object")
    return raw


def _load_env_block(config: dict[str, object], config_path: Path) -> dict[str, str]:
    """Return the settings in the "env" block of the config file.

    A block or key that cannot be used is left out and reported as a
    KlintWarning.
    """
    env_block = config.get("env", {})
    if not isinstance(env_block, dict):
        warnings.warn(
            f"The 'env' block in '{config_path}' is ignored: it must be a JSON object",
            KlintWarning,
            stacklevel=2,
        )
        return {}
    unknown = sorted(str(key) for key in env_block if key not in _KNOWN_ENV_KEYS)
    if unknown:
        warnings.warn(
            f"The 'env' block in '{config_path}' has unknown keys {unknown}, "
            f"which are ignored; known keys: {sorted(_KNOWN_ENV_KEYS)}",
            KlintWarning,
            stacklevel=2,
        )
    return {
        key: str(value)
        for key, value in env_block.items()
        if key in _KNOWN_ENV_KEYS and value is not None
    }


def _load_fallback_rule_packs(
    config: dict[str, object], config_path: Path
) -> tuple[Path, ...] | None:
    """Return the fallback packs the config file names; None when it names none.

    A relative path is taken from the folder of the config file. A value
    that is not a list of paths is ignored, and a path to no file is left
    out; each is reported as a KlintWarning.
    """
    if _FALLBACK_RULE_PACKS_KEY not in config:
        return None
    raw_paths = config[_FALLBACK_RULE_PACKS_KEY]
    if not isinstance(raw_paths, list) or not all(
        isinstance(raw_path, str) for raw_path in raw_paths
    ):
        warnings.warn(
            f"The '{_FALLBACK_RULE_PACKS_KEY}' key in '{config_path}' is ignored: "
            "it must be a list of paths",
            KlintWarning,
            stacklevel=2,
        )
        return None
    fallback_rule_packs: list[Path] = []
    for raw_path in raw_paths:
        path = (config_path.parent / raw_path).resolve()
        if path.is_file():
            fallback_rule_packs.append(path)
        else:
            warnings.warn(
                f"The '{_FALLBACK_RULE_PACKS_KEY}' key in '{config_path}' names "
                f"'{raw_path}', which is not a file; it is left out",
                KlintWarning,
                stacklevel=2,
            )
    return tuple(fallback_rule_packs)


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
    discovered_config_path: Path | None = None
    # The file that lists each language's file extensions.
    language_to_file_extensions_path: Path = field(
        default_factory=_locate_built_in_language_to_file_extensions
    )

    @classmethod
    def from_env(
        cls,
        target_path: Path | None = None,
        config_path: Path | None = None,
    ) -> "AppSettings":
        """Load the settings for an audit of ``target_path``.

        Each setting is taken from the first of these that sets it: the
        shell's environment variables, the "env" block of the config file,
        the built-in default. A relative path is taken from the working
        directory when the shell sets it, and from the folder of the config
        file when the file does. Nothing outside the returned value is
        changed.
        """
        active_config = config_path or find_project_config(target_path)
        config = _read_config(active_config)
        sources = [
            _SettingSource(
                description="the environment",
                key_to_value={
                    key: os.environ[key] for key in _KNOWN_ENV_KEYS if key in os.environ
                },
                base_folder=Path.cwd(),
            )
        ]
        fallback_rule_packs: tuple[Path, ...] | None = None
        if active_config is not None:
            sources.append(
                _SettingSource(
                    description=f"'{active_config}'",
                    key_to_value=_load_env_block(config, active_config),
                    base_folder=active_config.parent,
                )
            )
            fallback_rule_packs = _load_fallback_rule_packs(config, active_config)

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
                if fallback_rule_packs is None
                else fallback_rule_packs
            ),
            # When set, each variable names one file that replaces the
            # built-in packs for its command.
            file_contents_rule_pack_override=_resolve_setting_path(
                _find_setting("KEV_DEFAULT_RULES_PATH", sources)
            ),
            project_structure_rule_pack_override=_resolve_setting_path(
                _find_setting("KEV_DEFAULT_PROJECT_RULES_PATH", sources)
            ),
            discovered_config_path=active_config,
        )
