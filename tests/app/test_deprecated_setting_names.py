"""Old setting names: each still works for one release, with a warning."""

from pathlib import Path

import pytest

from klint.app.judge_mode import JudgeMode
from klint.app.settings import AppSettings
from klint.core.klint_warning import KlintWarning
from tests.support.builders import write_json


def _describe_deprecation(old_name: str, new_name: str, place: str) -> str:
    return (
        f"'{old_name}' {place} is deprecated and stops working in the next "
        f"release; use '{new_name}' instead"
    )


def test_old_judge_setting_names_in_the_shell_still_apply_with_a_warning(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env.update(
        {
            "KEV_MODE": "remote",
            "KEV_MODEL_NAME": "a-model",
            "KEV_BASE_URL": "http://judge:1",
            "KEV_API_KEY": "a-key",
        }
    )

    with pytest.warns(KlintWarning) as warned:
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.judge_mode is JudgeMode.REMOTE
    assert settings.model_name == "a-model"
    assert settings.judge_base_url == "http://judge:1"
    assert settings.judge_api_key == "a-key"
    assert sorted(str(warning.message) for warning in warned) == [
        _describe_deprecation(old_name, new_name, "in the environment")
        for old_name, new_name in [
            ("KEV_API_KEY", "KLINT_JUDGE_API_KEY"),
            ("KEV_BASE_URL", "KLINT_JUDGE_BASE_URL"),
            ("KEV_MODE", "KLINT_JUDGE_MODE"),
            ("KEV_MODEL_NAME", "KLINT_JUDGE_MODEL"),
        ]
    ]


@pytest.mark.usefixtures("shell_env")
def test_old_setting_name_in_klint_json_still_applies_with_a_warning(
    tmp_path: Path,
) -> None:
    config = write_json(tmp_path / "klint.json", {"env": {"KEV_MODE": "remote"}})

    with pytest.warns(KlintWarning) as warned:
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.judge_mode is JudgeMode.REMOTE
    assert [str(warning.message) for warning in warned] == [
        _describe_deprecation("KEV_MODE", "KLINT_JUDGE_MODE", f"in '{config}'")
    ]


def test_new_setting_name_wins_over_the_old_one_set_beside_it(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env.update({"KEV_MODE": "remote", "KLINT_JUDGE_MODE": "local"})

    with pytest.warns(KlintWarning, match="'KEV_MODE' in the environment"):
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.judge_mode is JudgeMode.LOCAL


def test_old_rule_replacement_names_still_apply_with_a_warning(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    file_pack = write_json(tmp_path / "file_rules.json", {})
    project_pack = write_json(tmp_path / "project_rules.json", {})
    shell_env["KEV_DEFAULT_RULES_PATH"] = str(file_pack)
    shell_env["KEV_DEFAULT_PROJECT_RULES_PATH"] = str(project_pack)

    with pytest.warns(KlintWarning) as warned:
        settings = AppSettings.from_env(tmp_path, None)

    assert settings.file_rule_replacement == file_pack
    assert settings.project_rule_replacement == project_pack
    assert sorted(str(warning.message) for warning in warned) == [
        _describe_deprecation(old_name, new_name, "in the environment")
        for old_name, new_name in [
            ("KEV_DEFAULT_PROJECT_RULES_PATH", "KLINT_REPLACE_PROJECT_RULES"),
            ("KEV_DEFAULT_RULES_PATH", "KLINT_REPLACE_FILE_RULES"),
        ]
    ]
