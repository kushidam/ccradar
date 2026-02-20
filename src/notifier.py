"""Slack Incoming Webhook を使った通知モジュール。"""

import logging
import os

import requests

from src.classifier import ClassifiedItem

logger = logging.getLogger(__name__)


def _build_blocks(version: str, items: list[ClassifiedItem]) -> list[dict]:
    """通知用の Slack Block Kit ブロックを構築する。"""
    features = [item for item in items if item.category == "Feature"]
    improvements = [item for item in items if item.category == "Improvement"]
    breakings = [item for item in items if item.category == "Breaking"]

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Claude Code {version} - Release Radar",
            },
        },
    ]

    if breakings:
        breaking_text = "\n".join(f"  - {b.summary}" for b in breakings)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:warning: Breaking Changes*\n{breaking_text}",
            },
        })

    if features:
        feature_text = "\n".join(f"  - {f.summary}" for f in features)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:sparkles: New Features*\n{feature_text}",
            },
        })

    if improvements:
        improvement_text = "\n".join(f"  - {i.summary}" for i in improvements)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:arrow_up: Improvements*\n{improvement_text}",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"<https://github.com/anthropics/claude-code/releases/tag/v{version}|View full release notes>",
            }
        ],
    })

    return blocks


def notify(version: str, items: list[ClassifiedItem]) -> None:
    """リリースの Slack 通知を送信する。

    Args:
        version: リリースバージョン文字列。
        items: 分類済み項目のリスト（Feature, Improvement, Breaking）。

    Raises:
        RuntimeError: SLACK_WEBHOOK_URL が未設定の場合。
        requests.HTTPError: Slack API がエラーを返した場合。
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        raise RuntimeError("SLACK_WEBHOOK_URL environment variable is not set")

    if not items:
        payload = {
            "text": f"Claude Code {version} がリリースされました（Bugfix のみ） <https://github.com/anthropics/claude-code/releases/tag/v{version}|Release Notes>",
        }
    else:
        blocks = _build_blocks(version, items)
        payload = {
            "blocks": blocks,
            "text": f"Claude Code {version} - new features and improvements detected",
        }

    response = requests.post(webhook_url, json=payload, timeout=30)
    response.raise_for_status()
    logger.info("Slack notification sent for version %s", version)


def format_dry_run(version: str, items: list[ClassifiedItem]) -> str:
    """dry-run 用に通知内容をフォーマットする。

    Args:
        version: リリースバージョン文字列。
        items: 分類済み項目のリスト。

    Returns:
        コンソール出力用のフォーマット済み文字列。
    """
    if not items:
        return f"[{version}] Release found, but no new features, improvements, or breaking changes (bugfix only)."

    features = [item for item in items if item.category == "Feature"]
    improvements = [item for item in items if item.category == "Improvement"]
    breakings = [item for item in items if item.category == "Breaking"]

    lines = [f"=== Claude Code {version} ==="]

    if breakings:
        lines.append("\n[Breaking Changes]")
        for b in breakings:
            lines.append(f"  - {b.summary}")

    if features:
        lines.append("\n[New Features]")
        for f in features:
            lines.append(f"  - {f.summary}")

    if improvements:
        lines.append("\n[Improvements]")
        for i in improvements:
            lines.append(f"  - {i.summary}")

    return "\n".join(lines)
