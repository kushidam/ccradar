"""処理済みバージョンの状態管理モジュール。"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "state.json")


def get_last_version() -> Optional[str]:
    """状態ファイルから最後に処理したバージョンを読み取る。

    Returns:
        最後に処理したバージョン文字列。ファイルが存在しない場合は None。
    """
    if not os.path.exists(STATE_FILE):
        logger.info("State file not found: %s", STATE_FILE)
        return None

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        version = data.get("last_version")
        logger.info("Last processed version: %s", version)
        return version
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read state file: %s", e)
        return None


def save_last_version(version: str) -> None:
    """最後に処理したバージョンを状態ファイルに保存する。

    Args:
        version: 保存するバージョン文字列。
    """
    data = {
        "last_version": version,
        "last_checked": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    logger.info("Saved last version: %s", version)
