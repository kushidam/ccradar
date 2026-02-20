"""Claude Code のリリース情報を取得する GitHub API クライアント。"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

REPO_OWNER = "anthropics"
REPO_NAME = "claude-code"
API_BASE = "https://api.github.com"


def _get_headers() -> dict:
    """リクエストヘッダーを構築する。GITHUB_TOKEN があれば認証ヘッダーを付与。"""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_releases(per_page: int = 30) -> list[dict]:
    """Claude Code リポジトリからリリース一覧を取得する。

    戻り値は published_at の降順（新しい順）のリリース dict のリスト。
    """
    url = f"{API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    params = {"per_page": per_page}

    response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
    response.raise_for_status()

    releases = response.json()
    logger.info("Fetched %d releases from %s/%s", len(releases), REPO_OWNER, REPO_NAME)
    return releases


def get_new_releases(last_version: Optional[str] = None) -> list[dict]:
    """指定バージョンより新しいリリースを取得する。

    Args:
        last_version: 最後に処理済みのバージョンタグ（例: "1.0.0"）。
                      None の場合は最新リリースのみ返す。

    Returns:
        リリース dict のリスト（古い順、順次処理用）。
    """
    releases = fetch_releases()

    if not releases:
        return []

    if last_version is None:
        logger.info("No last version found, returning latest release only")
        return [releases[0]]

    new_releases = []
    for release in releases:
        tag = release.get("tag_name", "").lstrip("v")
        if tag == last_version:
            break
        new_releases.append(release)

    # 時系列順に処理するため古い順に並び替え
    new_releases.reverse()
    logger.info("Found %d new release(s) since %s", len(new_releases), last_version)
    return new_releases


def get_release_by_tag(version: str) -> dict | None:
    """指定バージョンのリリースを取得する。見つからなければ None。"""
    tag = version if version.startswith("v") else f"v{version}"
    url = f"{API_BASE}/repos/{REPO_OWNER}/{REPO_NAME}/releases/tags/{tag}"

    response = requests.get(url, headers=_get_headers(), timeout=30)
    if response.status_code == 404:
        logger.warning("Release not found: %s", tag)
        return None
    response.raise_for_status()
    return response.json()


def get_release_body(release: dict) -> str:
    """リリース dict から本文（CHANGELOG 内容）を取得する。"""
    return release.get("body", "")


def get_release_version(release: dict) -> str:
    """リリース dict からバージョン文字列を取得する。"""
    return release.get("tag_name", "").lstrip("v")
