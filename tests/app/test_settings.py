"""Settings precedence: shell variables, then klint.json, then the defaults."""

import os
from pathlib import Path

import pytest

from klint.app.judge_mode import JudgeMode
from klint.app.settings import AppSettings
from klint.core.klint_warning import KlintWarning
from tests.support.builders import write_json, write_text
from tests.support.paths import (
    BUILT_IN_RULE_PACKS,
    DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
    FALLBACK_RULE_PACKS,
)


def _create_project(tmp_path: Path, env_block: dict[str, str] | None = None) -> Path:
    """Create a project folder, with a klint.json when ``env_block`` is given."""
    project = tmp_path / "project"
    project.mkdir()
    if env_block is not None:
        write_json(project / "klint.json", {"env": env_block, "rules": {}})
    return project


@pytest.mark.usefixtures("shell_env")
def test_built_in_defaults_apply_when_nothing_is_configured(tmp_path: Path) -> None:
    settings = AppSettings.from_env(_create_project(tmp_path), None)

    assert settings == AppSettings(
        model_name="jaredpalmer/kev-4b",
        judge_mode=JudgeMode.LOCAL,
        judge_base_url="http://127.0.0.1:8009",
        judge_api_key=None,
        built_in_rule_packs=BUILT_IN_RULE_PACKS,
        fallback_rule_packs=FALLBACK_RULE_PACKS,
        file_rule_replacement=None,
        project_rule_replacement=None,
        config_path=None,
        language_to_file_extensions_path=DEFAULT_LANGUAGE_TO_FILE_EXTENSIONS,
    )
    assert settings.language_to_file_extensions_path.is_file()


@pytest.mark.usefixtures("shell_env")
def test_klint_json_overrides_the_defaults(tmp_path: Path) -> None:
    project = _create_project(
        tmp_path,
        {"KLINT_JUDGE_MODEL": "from-json", "KLINT_JUDGE_BASE_URL": "http://json:1"},
    )

    settings = AppSettings.from_env(project, None)

    assert settings.model_name == "from-json"
    assert settings.judge_base_url == "http://json:1"
    assert settings.judge_api_key is None  # set nowhere, so the default
    assert settings.judge_mode == "local"  # set nowhere, so the default
    assert settings.config_path == project / "klint.json"


def test_shell_variable_overrides_klint_json(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env["KLINT_JUDGE_MODEL"] = "from-shell"
    project = _create_project(
        tmp_path, {"KLINT_JUDGE_MODEL": "from-json", "KLINT_JUDGE_MODE": "remote"}
    )

    settings = AppSettings.from_env(project, None)

    assert settings.model_name == "from-shell"
    assert settings.judge_mode == "remote"  # still taken from klint.json


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize("name", ["klint.json", ".klintrc.json", ".klintrc"])
def test_config_is_discovered_next_to_a_file_target(tmp_path: Path, name: str) -> None:
    project = _create_project(tmp_path)
    write_json(project / name, {"env": {"KLINT_JUDGE_MODEL": "found"}})
    target = project / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    settings = AppSettings.from_env(target, None)

    assert settings.config_path == project / name
    assert settings.model_name == "found"


@pytest.mark.usefixtures("shell_env")
def test_settings_in_a_rules_file_are_ignored_with_a_warning(tmp_path: Path) -> None:
    project = _create_project(tmp_path, {"KLINT_JUDGE_MODEL": "discovered"})
    rules_file = write_json(
        tmp_path / "custom.json",
        {
            "env": {"KLINT_JUDGE_MODEL": "from-rules-file"},
            "fallback_rule_packs": ["docs.json"],
            "rules": {},
        },
    )

    with pytest.warns(KlintWarning) as caught:
        settings = AppSettings.from_env(project, rules_file)

    # The project's klint.json is still found and applies.
    assert settings.model_name == "discovered"
    assert settings.config_path == project / "klint.json"
    assert settings.fallback_rule_packs == FALLBACK_RULE_PACKS
    assert [str(warning.message) for warning in caught] == [
        f"The '{key}' key in '{rules_file}' is ignored: settings come from "
        "environment variables and the project's klint.json, not from a "
        "--rules file"
        for key in ("env", "fallback_rule_packs")
    ]


@pytest.mark.usefixtures("shell_env")
def test_klint_json_given_as_the_rules_file_too_is_not_warned_about(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path, {"KLINT_JUDGE_MODEL": "discovered"})

    # An unexpected warning fails the test.
    settings = AppSettings.from_env(project, project / "klint.json")

    assert settings.model_name == "discovered"


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("content", "does_hold_rules"),
    [
        ({"env": {"KLINT_JUDGE_MODE": "remote"}}, False),
        ({"fallback_rule_packs": []}, False),
        ({"env": {}, "rules": {"a": {"type": "choice", "question": "?"}}}, True),
        ({"a": {"type": "choice", "question": "?"}}, True),
    ],
)
def test_klint_json_is_a_project_rule_pack_when_it_holds_rules(
    tmp_path: Path, content: dict[str, object], does_hold_rules: bool
) -> None:
    project = _create_project(tmp_path)
    config = write_json(project / "klint.json", content)

    settings = AppSettings.from_env(project, None)

    assert settings.project_rule_packs == ((config,) if does_hold_rules else ())


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize(
    ("content", "reason"),
    [("{not json", "is not valid JSON"), ("[]", "must be a JSON object")],
)
def test_klint_json_that_cannot_be_read_stops_with_an_error_naming_it(
    tmp_path: Path, content: str, reason: str
) -> None:
    project = _create_project(tmp_path)
    (project / "klint.json").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=rf"klint\.json' {reason}"):
        AppSettings.from_env(project, None)


@pytest.mark.usefixtures("shell_env")
def test_env_block_that_is_not_an_object_is_ignored_with_a_warning(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)
    write_json(project / "klint.json", {"env": "KLINT_JUDGE_MODE=remote", "rules": {}})

    with pytest.warns(KlintWarning, match="'env' block .* is ignored"):
        settings = AppSettings.from_env(project, None)

    assert settings.judge_mode == "local"


@pytest.mark.usefixtures("shell_env")
def test_unknown_env_key_is_ignored_with_a_warning_and_the_rest_applies(
    tmp_path: Path,
) -> None:
    project = _create_project(
        tmp_path, {"KLINT_JUDGE_MODLE": "typo", "KLINT_JUDGE_MODE": "remote"}
    )

    with pytest.warns(KlintWarning, match=r"unknown keys \['KLINT_JUDGE_MODLE'\]"):
        settings = AppSettings.from_env(project, None)

    assert settings.judge_mode == "remote"
    assert settings.model_name == "jaredpalmer/kev-4b"


@pytest.mark.usefixtures("shell_env")
def test_every_known_env_key_is_applied_without_a_warning(tmp_path: Path) -> None:
    pack = write_json(tmp_path / "pack.json", {})
    project = _create_project(
        tmp_path,
        {
            "KLINT_JUDGE_MODEL": "a-model",
            "KLINT_JUDGE_MODE": "remote",
            "KLINT_JUDGE_BASE_URL": "http://judge:1",
            "KLINT_JUDGE_API_KEY": "a-key",
            "KLINT_REPLACE_FILE_RULES": str(pack),
            "KLINT_REPLACE_PROJECT_RULES": str(pack),
        },
    )

    # An unexpected warning fails the test.
    settings = AppSettings.from_env(project, None)

    assert settings.model_name == "a-model"
    assert settings.judge_mode == "remote"
    assert settings.judge_base_url == "http://judge:1"
    assert settings.judge_api_key == "a-key"
    assert settings.file_rule_replacement == pack
    assert settings.project_rule_replacement == pack


def test_rule_replacement_variables_name_the_pack_that_replaces_the_built_in_ones(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    file_pack = write_json(tmp_path / "file_rules.json", {})
    project_pack = write_json(tmp_path / "project_rules.json", {})
    shell_env["KLINT_REPLACE_FILE_RULES"] = str(file_pack)
    shell_env["KLINT_REPLACE_PROJECT_RULES"] = str(project_pack)

    settings = AppSettings.from_env(_create_project(tmp_path), None)

    # Each command replaces the built-in packs with its own; see the command
    # tests. The built-in packs stay as they are for the other command.
    assert settings.file_rule_replacement == file_pack
    assert settings.project_rule_replacement == project_pack
    assert settings.built_in_rule_packs == BUILT_IN_RULE_PACKS


def test_relative_rule_replacement_set_in_the_shell_is_taken_from_the_working_directory(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    # The fixture's working directory, not klint's own folder.
    shell_env["KLINT_REPLACE_FILE_RULES"] = "rules/file_rules.json"

    settings = AppSettings.from_env(_create_project(tmp_path), None)

    expected = (Path.cwd() / "rules" / "file_rules.json").resolve()
    assert settings.file_rule_replacement == expected


@pytest.mark.usefixtures("shell_env")
def test_relative_rule_replacement_set_in_klint_json_is_taken_from_its_folder(
    tmp_path: Path,
) -> None:
    project = _create_project(
        tmp_path, {"KLINT_REPLACE_PROJECT_RULES": "rules/project_rules.json"}
    )

    settings = AppSettings.from_env(project, None)

    expected = (project / "rules" / "project_rules.json").resolve()
    assert settings.project_rule_replacement == expected


@pytest.mark.usefixtures("shell_env")
def test_fallback_rule_packs_in_klint_json_replace_the_built_in_ones(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)
    in_project = write_text(project / "rules" / "docs.json", "{}")
    elsewhere = write_text(tmp_path / "prose.json", "{}")
    write_json(
        project / "klint.json",
        {"fallback_rule_packs": ["rules/docs.json", str(elsewhere)]},
    )

    settings = AppSettings.from_env(project, None)

    # A relative path is taken from the folder of klint.json.
    assert settings.fallback_rule_packs == (in_project, elsewhere)
    assert settings.built_in_rule_packs == BUILT_IN_RULE_PACKS


@pytest.mark.usefixtures("shell_env")
def test_fallback_rule_packs_that_are_not_a_list_of_paths_are_ignored_with_a_warning(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)
    write_json(project / "klint.json", {"fallback_rule_packs": "docs.json"})

    with pytest.warns(KlintWarning, match="'fallback_rule_packs' key .* is ignored"):
        settings = AppSettings.from_env(project, None)

    assert settings.fallback_rule_packs == FALLBACK_RULE_PACKS


@pytest.mark.usefixtures("shell_env")
def test_fallback_rule_pack_that_is_not_a_file_is_left_out_with_a_warning(
    tmp_path: Path,
) -> None:
    project = _create_project(tmp_path)
    kept = write_json(project / "docs.json", {})
    write_json(
        project / "klint.json", {"fallback_rule_packs": ["absent.json", "docs.json"]}
    )

    with pytest.warns(KlintWarning, match="names 'absent.json', which is not a file"):
        settings = AppSettings.from_env(project, None)

    assert settings.fallback_rule_packs == (kept,)


@pytest.mark.parametrize(
    ("raw_mode", "expected"),
    [
        ("local", JudgeMode.LOCAL),
        ("remote", JudgeMode.REMOTE),
        ("Remote", JudgeMode.REMOTE),
    ],
)
def test_mode_is_read_as_a_judge_mode_in_any_case(
    shell_env: dict[str, str], tmp_path: Path, raw_mode: str, expected: JudgeMode
) -> None:
    shell_env["KLINT_JUDGE_MODE"] = raw_mode

    settings = AppSettings.from_env(_create_project(tmp_path), None)

    assert settings.judge_mode is expected


def test_unknown_mode_stops_with_an_error_listing_the_valid_values(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env["KLINT_JUDGE_MODE"] = "locl"

    with pytest.raises(
        ValueError,
        match=r"KLINT_JUDGE_MODE 'locl'.* is not a judge mode; valid values: "
        r"\['local', 'remote'\]",
    ):
        AppSettings.from_env(_create_project(tmp_path), None)


def test_loading_the_settings_leaves_the_environment_as_it_was(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env["KLINT_JUDGE_API_KEY"] = "from-shell"
    project = _create_project(tmp_path, {"KLINT_JUDGE_MODEL": "from-json"})
    environment_before = dict(os.environ)

    settings = AppSettings.from_env(project, None)

    assert dict(os.environ) == environment_before
    assert (settings.judge_api_key, settings.model_name) == ("from-shell", "from-json")
    # A later load without that klint.json sees none of its values.
    other_project = tmp_path / "other"
    other_project.mkdir()
    later = AppSettings.from_env(other_project, None)
    assert (later.judge_api_key, later.model_name, later.judge_base_url) == (
        "from-shell",
        "jaredpalmer/kev-4b",
        "http://127.0.0.1:8009",
    )
