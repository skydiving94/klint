import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MODEL_NAME = "jaredpalmer/kev-4b"
_DEFAULT_KEV_MODE = "local"
_DEFAULT_RULES_FILE = _PACKAGE_ROOT / "resources" / "default_rules.json"
_DEFAULT_PROJECT_RULES_FILE = (
    _PACKAGE_ROOT / "resources" / "default_project_rules.json"
)
CONFIG_FILENAMES = ("klint.json", ".klintrc.json", ".klintrc")


def find_project_config(start_path: Optional[Path] = None) -> Optional[Path]:
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


def _load_json_env_overrides(config_path: Optional[Path]) -> Dict[str, str]:
    if config_path is None or not config_path.is_file():
        return {}
    try:
        raw: Dict[str, Any] = json.loads(
            config_path.read_text(encoding="utf-8")
        )
    except Exception:
        return {}
    env_block = raw.get("env", {})
    if not isinstance(env_block, dict):
        return {}
    return {str(k): str(v) for k, v in env_block.items() if v is not None}


def _load_klint_dotenv(dotenv_path: Optional[Path] = None) -> None:
    """Load klint's own .env / .env.example as lowest-priority defaults."""
    target_env = dotenv_path or (_PACKAGE_ROOT / ".env")
    if not target_env.is_file():
        target_env = _PACKAGE_ROOT / ".env.example"
    if not target_env.is_file():
        return

    for raw_line in target_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def _resolve_resource_path(raw_path: str | Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or candidate.exists():
        return candidate.resolve()
    return (_PACKAGE_ROOT / candidate).resolve()


@dataclass(frozen=True)
class AppSettings:
    model_name: str
    default_rules_path: Path
    kev_mode: str = _DEFAULT_KEV_MODE
    kev_base_url: str = "http://127.0.0.1:8009"
    kev_api_key: Optional[str] = None
    default_project_rules_path: Optional[Path] = None
    discovered_config_path: Optional[Path] = None

    @classmethod
    def from_env(
        cls,
        target_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        dotenv_path: Optional[Path] = None,
    ) -> "AppSettings":
        # 1. Capture any shell variables explicitly exported by the user
        shell_env = dict(os.environ)

        # 2. Load klint's internal .env / .env.example as fallback defaults
        _load_klint_dotenv(dotenv_path)

        # 3. Check explicit --rules config file or auto-discovered klint.json
        active_config = config_path or find_project_config(target_path)
        json_env = _load_json_env_overrides(active_config)

        def _get_setting(
            key: str, default: Optional[str] = None
        ) -> Optional[str]:
            # Priority: Shell Export > Project klint.json "env" > klint .env > Default
            if key in shell_env and shell_env[key]:
                return shell_env[key]
            if key in json_env and json_env[key]:
                return json_env[key]
            return os.environ.get(key) or default

        model_name = _get_setting("KEV_MODEL_NAME", _DEFAULT_MODEL_NAME)
        rules_path = _get_setting(
            "KEV_DEFAULT_RULES_PATH", str(_DEFAULT_RULES_FILE)
        )
        project_rules_path = _get_setting(
            "KEV_DEFAULT_PROJECT_RULES_PATH", str(_DEFAULT_PROJECT_RULES_FILE)
        )
        kev_mode = (
            _get_setting("KEV_MODE", _DEFAULT_KEV_MODE) or _DEFAULT_KEV_MODE
        ).lower()
        kev_base_url = (
            _get_setting("KEV_BASE_URL", "http://127.0.0.1:8009")
            or "http://127.0.0.1:8009"
        )
        kev_api_key = _get_setting("KEV_API_KEY") or None

        assert model_name is not None and rules_path is not None
        return cls(
            model_name=model_name,
            default_rules_path=_resolve_resource_path(rules_path),
            kev_mode=kev_mode,
            kev_base_url=kev_base_url,
            kev_api_key=kev_api_key,
            default_project_rules_path=(
                _resolve_resource_path(project_rules_path)
                if project_rules_path
                else None
            ),
            discovered_config_path=active_config,
        )
