"""A project's klint.json: the settings and rules a project keeps for klint."""

import json
import warnings
from dataclasses import dataclass
from pathlib import Path

from klint.core.klint_warning import KlintWarning

CONFIG_FILENAMES = ("klint.json", ".klintrc.json", ".klintrc")
# The settings an environment variable, or the "env" block of a klint.json,
# may set.
KNOWN_SETTING_NAMES = frozenset(
    {
        "KEV_MODEL_NAME",
        "KEV_DEFAULT_RULES_PATH",
        "KEV_DEFAULT_PROJECT_RULES_PATH",
        "KEV_MODE",
        "KEV_BASE_URL",
        "KEV_API_KEY",
    }
)
_ENV_BLOCK_KEY = "env"
# The key of a klint.json that replaces the built-in fallback packs.
_FALLBACK_RULE_PACKS_KEY = "fallback_rule_packs"
# The keys of a klint.json that hold settings rather than rules.
_SETTING_KEYS = frozenset({_ENV_BLOCK_KEY, _FALLBACK_RULE_PACKS_KEY})


@dataclass(frozen=True)
class ProjectConfig:
    """A klint.json as read.

    setting_name_to_value holds what its "env" block sets. fallback_rule_packs
    are the packs it names in place of the built-in ones; None when it names
    none. does_hold_rules is True when it also holds rules, under "rules" or
    at its top level.
    """

    path: Path
    setting_name_to_value: dict[str, str]
    fallback_rule_packs: tuple[Path, ...] | None
    does_hold_rules: bool


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


def read_project_config(config_path: Path) -> ProjectConfig:
    """Read the klint.json at ``config_path``.

    Raises ValueError naming the file when it cannot be read as a JSON
    object. A part that cannot be used is left out and reported as a
    KlintWarning.
    """
    config = _read_json_object(config_path)
    return ProjectConfig(
        path=config_path,
        setting_name_to_value=_load_env_block(config, config_path),
        fallback_rule_packs=_load_fallback_rule_packs(config, config_path),
        does_hold_rules=any(key not in _SETTING_KEYS for key in config),
    )


def warn_about_settings_in_rules_file(rules_path: Path) -> None:
    """Warn about each setting in the rules file at ``rules_path``; none applies.

    Settings come only from the environment and the project's klint.json. A
    file that cannot be read is left for the rule loader to report.
    """
    try:
        rules_file = _read_json_object(rules_path)
    except (OSError, ValueError):
        return
    for key in sorted(_SETTING_KEYS & set(map(str, rules_file))):
        _warn(
            f"The '{key}' key in '{rules_path}' is ignored: settings come from "
            "environment variables and the project's klint.json, not from a "
            "--rules file"
        )


def _read_json_object(config_path: Path) -> dict[object, object]:
    """Return the JSON object in ``config_path``.

    Raises ValueError naming the file when it cannot be read as one.
    """
    try:
        raw: object = json.loads(config_path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise ValueError(f"'{config_path}' is not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"'{config_path}' must be a JSON object")
    return raw


def _load_env_block(config: dict[object, object], config_path: Path) -> dict[str, str]:
    """Return the settings in the "env" block of the config file.

    A block or key that cannot be used is left out and reported as a
    KlintWarning.
    """
    env_block = config.get(_ENV_BLOCK_KEY, {})
    if not isinstance(env_block, dict):
        _warn(
            f"The '{_ENV_BLOCK_KEY}' block in '{config_path}' is ignored: it must "
            "be a JSON object"
        )
        return {}
    unknown = sorted(str(key) for key in env_block if key not in KNOWN_SETTING_NAMES)
    if unknown:
        _warn(
            f"The '{_ENV_BLOCK_KEY}' block in '{config_path}' has unknown keys "
            f"{unknown}, which are ignored; known keys: {sorted(KNOWN_SETTING_NAMES)}"
        )
    return {
        str(key): str(value)
        for key, value in env_block.items()
        if key in KNOWN_SETTING_NAMES and value is not None
    }


def _load_fallback_rule_packs(
    config: dict[object, object], config_path: Path
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
        _warn(
            f"The '{_FALLBACK_RULE_PACKS_KEY}' key in '{config_path}' is ignored: "
            "it must be a list of paths"
        )
        return None
    fallback_rule_packs: list[Path] = []
    for raw_path in raw_paths:
        path = (config_path.parent / raw_path).resolve()
        if path.is_file():
            fallback_rule_packs.append(path)
        else:
            _warn(
                f"The '{_FALLBACK_RULE_PACKS_KEY}' key in '{config_path}' names "
                f"'{raw_path}', which is not a file; it is left out"
            )
    return tuple(fallback_rule_packs)


def _warn(message: str) -> None:
    warnings.warn(message, KlintWarning, stacklevel=3)
