import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("CONFIG_DIR", "/data"))
CONFIG_FILE = CONFIG_DIR / "config.json"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_api_key() -> str | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    key = data.get("api_key")
    return key if isinstance(key, str) and key.strip() else None


def save_api_key(api_key: str) -> None:
    ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps({"api_key": api_key.strip()}))


def mask_api_key(api_key: str) -> str:
    if len(api_key) <= 8:
        return "••••••••"
    return f"{api_key[:4]}…{api_key[-4:]}"
