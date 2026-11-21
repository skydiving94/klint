"""AppSettings: what one audit runs with, loaded from the shell and klint.json."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import assert_never

from klint.app.judge_mode import JudgeMode
from klint.app.project_config import (
    find_project_config,
    read_project_config,
    warn_about_settings_in_rules_file,
)
from klint.app.settings.built_in_packs import (
    locate_built_in_fallback_rule_packs,
    locate_built_in_language_to_file_extensions,
    locate_built_in_rule_packs,
    locate_built_in_tag_detection,
)
from klint.app.settings.setting_sources import (
    find_setting,
    read_answer_cache_setting,
    read_commit_min_confidence_setting,
    read_config_source,
    read_environment_source,
    read_judge_mode,
    resolve_setting_path,
)
from klint.core.models.rules import RuleExclusion
from klint.core.models.scanning import FileTraitsOverride

# The model and the server address the judge uses unless a setting names others.
_DEFAULT_MODEL_NAME = "jaredpalmer/kev-4b"
_DEFAULT_BASE_URL = "http://127.0.0.1:8009"


@dataclass(frozen=True)
class AppSettings:
    model_name: str
    judge_mode: JudgeMode = JudgeMode.LOCAL
    judge_base_url: str = _DEFAULT_BASE_URL
    judge_api_key: str | None = None
    # The packs chosen by the traits of each file, and the packs a file whose
    # language is not identified is asked instead.
    built_in_rule_packs: tuple[Path, ...] = field(
        default_factory=locate_built_in_rule_packs
    )
    fallback_rule_packs: tuple[Path, ...] = field(
        default_factory=locate_built_in_fallback_rule_packs
    )
    # A file that replaces every built-in pack for one command, klint or
    # klint-structure; its rules are then asked about every file.
    file_rule_replacement: Path | None = None
    project_rule_replacement: Path | None = None
    # The project's klint.json, and the files whose rules merge over the
    # loaded packs for every file: the klint.json when it holds rules.
    config_path: Path | None = None
    project_rule_packs: tuple[Path, ...] = ()
    # The file that lists each language's file extensions.
    language_to_file_extensions_path: Path = field(
        default_factory=locate_built_in_language_to_file_extensions
    )
    # The file of tables that tell which side of a project a file belongs to.
    tag_detection_path: Path = field(default_factory=locate_built_in_tag_detection)
    # What the project's klint.json says about some files, over what is
    # detected; the first entry whose glob matches a file decides.
    file_traits_overrides: tuple[FileTraitsOverride, ...] = ()
    # The project's layers as its klint.json lists them, outermost first.
    layers: tuple[str, ...] = ()
    # The rules the project's klint.json turns off for some of its paths.
    rule_exclusions: tuple[RuleExclusion, ...] = ()
    # Where the judge's answers are kept between runs; None keeps none.
    # Settings built in code keep none unless they ask to, so that only a
    # run from the shell, or the hook, writes to the user's cache folder.
    answer_cache_folder: Path | None = None
    # The least confidence a failure needs to block a commit; None: the judge's.
    commit_min_confidence: float | None = None

    @classmethod
    def from_env(
        cls,
        target_path: Path | None = None,
        custom_rules_path: Path | None = None,
    ) -> "AppSettings":
        """Load the settings for an audit of ``target_path``.

        Each setting is taken from the first of these that sets it: the
        shell's environment variables, the "env" block of the project's
        klint.json, the built-in default. A relative path is taken from the
        working directory when the shell sets it, and from the folder of the
        klint.json when the file does. ``custom_rules_path``, the file given with
        --rules, holds rules only: a setting in it is ignored with a warning.
        Nothing outside the returned value is changed.
        """
        config_path = find_project_config(target_path)
        config = None if config_path is None else read_project_config(config_path)
        if custom_rules_path is not None and (
            config_path is None or custom_rules_path.resolve() != config_path.resolve()
        ):
            warn_about_settings_in_rules_file(custom_rules_path)
        sources = [read_environment_source()]
        if config is not None:
            sources.append(read_config_source(config))

        def _get_setting(key: str) -> str | None:
            setting = find_setting(key, sources)
            return None if setting is None else setting.value

        return cls(
            model_name=_get_setting("KLINT_JUDGE_MODEL") or _DEFAULT_MODEL_NAME,
            judge_mode=read_judge_mode(find_setting("KLINT_JUDGE_MODE", sources)),
            judge_base_url=_get_setting("KLINT_JUDGE_BASE_URL") or _DEFAULT_BASE_URL,
            judge_api_key=_get_setting("KLINT_JUDGE_API_KEY"),
            fallback_rule_packs=(
                locate_built_in_fallback_rule_packs()
                if config is None or config.fallback_rule_packs is None
                else config.fallback_rule_packs
            ),
            # When set, each variable names one file that replaces the
            # built-in packs for its command.
            file_rule_replacement=resolve_setting_path(
                find_setting("KLINT_REPLACE_FILE_RULES", sources)
            ),
            project_rule_replacement=resolve_setting_path(
                find_setting("KLINT_REPLACE_PROJECT_RULES", sources)
            ),
            config_path=config_path,
            project_rule_packs=(
                (config.path,) if config is not None and config.does_hold_rules else ()
            ),
            file_traits_overrides=(
                () if config is None else config.file_traits_overrides
            ),
            layers=() if config is None else config.layers,
            rule_exclusions=() if config is None else config.rule_exclusions,
            answer_cache_folder=read_answer_cache_setting(
                find_setting("KLINT_ANSWER_CACHE", sources)
            ),
            commit_min_confidence=read_commit_min_confidence_setting(
                find_setting("KLINT_COMMIT_MIN_CONFIDENCE", sources)
            ),
        )

    def describe_judge(self) -> str:
        """Say which judge these settings choose and where it runs, never the key.

        The answer cache's folder follows when the cache is on.
        """
        cache_note = (
            ""
            if self.answer_cache_folder is None
            else f"; answer cache at {self.answer_cache_folder}"
        )
        match self.judge_mode:
            case JudgeMode.LOCAL:
                return f"{self.model_name}, run in this process (local){cache_note}"
            case JudgeMode.REMOTE:
                key_note = "API key set" if self.judge_api_key else "no API key"
                where = f"at {self.judge_base_url}"
                return f"{self.model_name} {where} (remote, {key_note}){cache_note}"
            case _:
                assert_never(self.judge_mode)
