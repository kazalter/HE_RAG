from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = PACKAGE_DIR.parent / ".rag_config.json"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}

    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_deepseek_api_key() -> str:
    # 优先级：环境变量 DEEPSEEK_API_KEY > 本地配置文件。
    # 这样 Key 可以不落盘，避免明文写进 .rag_config.json 进而泄露。
    env_value = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env_value:
        return env_value

    value = load_config().get("deepseek_api_key", "")
    return str(value).strip()


def set_deepseek_api_key(api_key: str) -> None:
    config = load_config()
    config["deepseek_api_key"] = api_key.strip()
    save_config(config)


def clear_deepseek_api_key() -> None:
    config = load_config()
    config.pop("deepseek_api_key", None)
    save_config(config)


def has_deepseek_api_key() -> bool:
    return bool(get_deepseek_api_key())
