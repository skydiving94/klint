"""Removed setting names: each is ignored, with a warning naming its replacement."""

from pathlib import Path

import pytest

from klint.app import AppSettings, JudgeMode
from klint.core import KlintWarning
from tests.support.builders import write_json


def _describe_removal(old_name: str, new_name: str, place: str) -> str:
    return f"'{old_name}' {place} was removed; use '{new_name}' instead"


def test_removed_setting_names_in_the_shell_are_ignored_with_a_warning(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    defaults = AppSettings.from_env(tmp_path, None)
    shell_env.update(
        {
            "KEV_MODE": "remote",
            "KEV_MODEL_NAME": "a-model",
            "KEV_BASE_URL": "http://judge:1",
            "KEV_API_KEY": "a-key",
            "KEV_DEFAULT_RULES_PATH": "file_rules.json",
            "KEV_DEFAULT_PROJECT_RULES_PATH": "project_rules.json",
        }
    )

    with pytest.warns(KlintWarning) as warned:
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.judge_mode is JudgeMode.LOCAL
    assert settings.model_name == defaults.model_name
    assert settings.judge_base_url == defaults.judge_base_url
    assert settings.judge_api_key is None
    assert settings.file_rule_replacement is None
    assert settings.project_rule_replacement is None
    assert [str(warning.message) for warning in warned] == [
        _describe_removal(old_name, new_name, "in the environment")
        for old_name, new_name in [
            ("KEV_API_KEY", "KLINT_JUDGE_API_KEY"),
            ("KEV_BASE_URL", "KLINT_JUDGE_BASE_URL"),
            ("KEV_DEFAULT_PROJECT_RULES_PATH", "KLINT_REPLACE_PROJECT_RULES"),
            ("KEV_DEFAULT_RULES_PATH", "KLINT_REPLACE_FILE_RULES"),
            ("KEV_MODE", "KLINT_JUDGE_MODE"),
            ("KEV_MODEL_NAME", "KLINT_JUDGE_MODEL"),
        ]
    ]


@pytest.mark.usefixtures("shell_env")
def test_removed_setting_name_in_klint_json_is_ignored_with_a_warning(
    tmp_path: Path,
) -> None:
    config = write_json(tmp_path / "klint.json", {"env": {"KEV_MODE": "remote"}})

    with pytest.warns(KlintWarning) as warned:
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.judge_mode is JudgeMode.LOCAL
    assert [str(warning.message) for warning in warned] == [
        _describe_removal("KEV_MODE", "KLINT_JUDGE_MODE", f"in '{config}'")
    ]
