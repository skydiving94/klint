"""The "rule_exclusions" of a klint.json: rules a project turns off for some paths."""

import warnings
from pathlib import Path

from klint.core import KlintWarning
from klint.core.models.rules import RuleExclusion

# The key of a klint.json that turns rules off for some paths.
RULE_EXCLUSIONS_KEY = "rule_exclusions"
_RULE_EXCLUSION_FIELD_NAMES = frozenset({"rule_id", "paths", "reason"})


def load_rule_exclusions(
    config: dict[object, object], config_path: Path
) -> tuple[RuleExclusion, ...]:
    """Return the "rule_exclusions" entries of the config file, in file order.

    Each entry is an object with exactly a "rule_id", "paths", a list of
    globs matched from the folder of the config file, and a "reason". A
    value that is not a list is ignored and an entry that cannot be used is
    left out; each is reported as a KlintWarning.
    """
    raw_entries = config.get(RULE_EXCLUSIONS_KEY, [])
    if not isinstance(raw_entries, list):
        _warn(
            f"The '{RULE_EXCLUSIONS_KEY}' key in '{config_path}' is ignored: it "
            "must be a list of objects"
        )
        return ()
    exclusions = (
        _read_rule_exclusion(raw_entry, index, config_path)
        for index, raw_entry in enumerate(raw_entries)
    )
    return tuple(exclusion for exclusion in exclusions if exclusion is not None)


def _read_rule_exclusion(
    raw_entry: object, index: int, config_path: Path
) -> RuleExclusion | None:
    """Return one "rule_exclusions" entry; None, with a warning, when unusable."""
    description = f"Entry {index} of '{RULE_EXCLUSIONS_KEY}' in '{config_path}'"
    if not isinstance(raw_entry, dict) or set(raw_entry) != _RULE_EXCLUSION_FIELD_NAMES:
        _warn(
            f"{description} is left out: it must be an object with exactly "
            f"{sorted(_RULE_EXCLUSION_FIELD_NAMES)}"
        )
        return None
    rule_id = raw_entry["rule_id"]
    paths = raw_entry["paths"]
    reason = raw_entry["reason"]
    if not isinstance(rule_id, str) or not rule_id:
        _warn(f"{description} is left out: its 'rule_id' must be a non-empty string")
        return None
    if not (
        isinstance(paths, list)
        and paths
        and all(isinstance(glob, str) and glob for glob in paths)
    ):
        _warn(f"{description} is left out: its 'paths' must be a list of globs")
        return None
    if not isinstance(reason, str) or not reason.strip():
        _warn(f"{description} is left out: its 'reason' must say why")
        return None
    return RuleExclusion(
        base_directory=config_path.parent.resolve(),
        rule_id=rule_id,
        paths=tuple(paths),
        reason=reason,
    )


def _warn(message: str) -> None:
    warnings.warn(message, KlintWarning, stacklevel=3)
