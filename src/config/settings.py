import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _load_dotenv(dotenv_path: Path = Path(".env")) -> None:
    if not dotenv_path.is_file():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class AppSettings:
    model_name: str
    default_rules_path: Path
    kev_mode: str = "remote"
    kev_base_url: str = "http://127.0.0.1:8009"
    kev_api_key: Optional[str] = None

    @classmethod
    def from_env(cls, dotenv_path: Path = Path(".env")) -> "AppSettings":
        _load_dotenv(dotenv_path)

        model_name = os.environ.get("KEV_MODEL_NAME")
        rules_path = os.environ.get("KEV_DEFAULT_RULES_PATH")

        if not model_name or not rules_path:
            raise EnvironmentError(
                "Missing required environment variables: "
                "KEV_MODEL_NAME and KEV_DEFAULT_RULES_PATH must be set."
            )

        return cls(
            model_name=model_name,
            default_rules_path=Path(rules_path),
            kev_mode=os.environ.get("KEV_MODE", "remote").lower(),
            kev_base_url=os.environ.get(
                "KEV_BASE_URL", "http://127.0.0.1:8009"),
            kev_api_key=os.environ.get("KEV_API_KEY") or None,
        )
