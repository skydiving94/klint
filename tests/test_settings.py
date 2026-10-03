"""Settings precedence: shell variables, klint.json, klint's own .env, defaults."""

import os
from pathlib import Path

import pytest

from src.app.settings import AppSettings
from tests.helpers import DEFAULT_PROJECT_RULES, DEFAULT_RULE_PACKS, write_json


@pytest.fixture
def shell_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    """Give the test a private environment with no KEV_* variables set.

    Settings loading writes into ``os.environ``, so each test gets its own
    copy. The working directory moves to an empty folder so that no stray
    klint.json is discovered there.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("KEV_")}
    monkeypatch.setattr(os, "environ", env)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return env


def _dotenv(tmp_path: Path, text: str = "") -> Path:
    path = tmp_path / "klint.env"
    path.write_text(text, encoding="utf-8")
    return path


def _project(tmp_path: Path, env_block: dict[str, str] | None = None) -> Path:
    """Create a project folder, with a klint.json when ``env_block`` is given."""
    project = tmp_path / "project"
    project.mkdir()
    if env_block is not None:
        write_json(project / "klint.json", {"env": env_block, "rules": {}})
    return project


@pytest.mark.usefixtures("shell_env")
def test_built_in_defaults_apply_when_nothing_is_configured(tmp_path: Path) -> None:
    settings = AppSettings.from_env(_project(tmp_path), None, _dotenv(tmp_path))

    assert settings == AppSettings(
        model_name="jaredpalmer/kev-4b",
        default_rules_paths=DEFAULT_RULE_PACKS,
        kev_mode="local",
        kev_base_url="http://127.0.0.1:8009",
        kev_api_key=None,
        default_project_rules_paths=(DEFAULT_PROJECT_RULES,),
        discovered_config_path=None,
    )


@pytest.mark.usefixtures("shell_env")
def test_klint_dotenv_overrides_the_defaults(tmp_path: Path) -> None:
    dotenv = _dotenv(
        tmp_path, "# comment\n\nKEV_MODEL_NAME = 'from-dotenv'\nKEV_MODE=REMOTE\n"
    )

    settings = AppSettings.from_env(_project(tmp_path), None, dotenv)

    assert settings.model_name == "from-dotenv"
    assert settings.kev_mode == "remote"


@pytest.mark.usefixtures("shell_env")
def test_klint_json_overrides_klint_dotenv_and_defaults(tmp_path: Path) -> None:
    project = _project(
        tmp_path, {"KEV_MODEL_NAME": "from-json", "KEV_BASE_URL": "http://json:1"}
    )
    dotenv = _dotenv(tmp_path, "KEV_MODEL_NAME=from-dotenv\nKEV_API_KEY=dotenv-key\n")

    settings = AppSettings.from_env(project, None, dotenv)

    assert settings.model_name == "from-json"
    assert settings.kev_base_url == "http://json:1"
    assert settings.kev_api_key == "dotenv-key"  # not set in klint.json
    assert settings.kev_mode == "local"  # set nowhere, so the default
    assert settings.discovered_config_path == project / "klint.json"


def test_shell_variable_overrides_klint_json(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    shell_env["KEV_MODEL_NAME"] = "from-shell"
    project = _project(tmp_path, {"KEV_MODEL_NAME": "from-json", "KEV_MODE": "remote"})

    settings = AppSettings.from_env(project, None, _dotenv(tmp_path))

    assert settings.model_name == "from-shell"
    assert settings.kev_mode == "remote"  # still taken from klint.json


@pytest.mark.usefixtures("shell_env")
@pytest.mark.parametrize("name", ["klint.json", ".klintrc.json", ".klintrc"])
def test_config_is_discovered_next_to_a_file_target(tmp_path: Path, name: str) -> None:
    project = _project(tmp_path)
    write_json(project / name, {"env": {"KEV_MODEL_NAME": "found"}})
    target = project / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    settings = AppSettings.from_env(target, None, _dotenv(tmp_path))

    assert settings.discovered_config_path == project / name
    assert settings.model_name == "found"


@pytest.mark.usefixtures("shell_env")
def test_explicit_config_path_wins_over_a_discovered_one(tmp_path: Path) -> None:
    project = _project(tmp_path, {"KEV_MODEL_NAME": "discovered"})
    explicit = write_json(
        tmp_path / "custom.json", {"env": {"KEV_MODEL_NAME": "explicit"}}
    )

    settings = AppSettings.from_env(project, explicit, _dotenv(tmp_path))

    assert settings.model_name == "explicit"
    assert settings.discovered_config_path == explicit


@pytest.mark.usefixtures("shell_env")
def test_unreadable_klint_json_is_ignored_for_settings(tmp_path: Path) -> None:
    project = _project(tmp_path)
    (project / "klint.json").write_text("{not json", encoding="utf-8")

    settings = AppSettings.from_env(project, None, _dotenv(tmp_path))

    assert settings.model_name == "jaredpalmer/kev-4b"
    assert settings.discovered_config_path == project / "klint.json"


def test_rules_path_variable_replaces_every_built_in_pack(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    file_pack = write_json(tmp_path / "file_rules.json", {})
    project_pack = write_json(tmp_path / "project_rules.json", {})
    shell_env["KEV_DEFAULT_RULES_PATH"] = str(file_pack)
    shell_env["KEV_DEFAULT_PROJECT_RULES_PATH"] = str(project_pack)

    settings = AppSettings.from_env(_project(tmp_path), None, _dotenv(tmp_path))

    assert settings.default_rules_paths == (file_pack,)
    assert settings.default_project_rules_paths == (project_pack,)


def test_relative_rules_path_resolves_against_the_klint_repo(
    shell_env: dict[str, str], tmp_path: Path
) -> None:
    relative = "src/resources/catalog/code/python/project_structure.json"
    shell_env["KEV_DEFAULT_RULES_PATH"] = relative

    settings = AppSettings.from_env(_project(tmp_path), None, _dotenv(tmp_path))

    assert settings.default_rules_paths == (DEFAULT_PROJECT_RULES,)
