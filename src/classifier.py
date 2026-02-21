"""Gemini API を使用した LLM ベースの分類・要約モジュール。"""

import json
import logging
import os
from dataclasses import dataclass

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from src.categories import NOTIFY_CATEGORIES, Category
from src.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Gemini クライアントを取得する（シングルトン）。"""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is not set")
        _client = genai.Client(api_key=api_key)
    return _client


@dataclass
class ClassifiedItem:
    """分類・要約済みのリリース項目。"""

    category: Category
    summary: str
    original: str = ""  # 元の箇条書きテキスト


def classify_release(body: str) -> list[ClassifiedItem]:
    """Gemini API を使ってリリース内容を分類・要約する。

    Args:
        body: リリースの本文テキスト（CHANGELOG 内容）。

    Returns:
        Feature, Improvement, Breaking, Change に該当する ClassifiedItem のリスト。
        該当なしの場合は空リスト。
    """
    if not body or not body.strip():
        logger.info("Empty release body, skipping classification")
        return []

    model_name = os.environ.get("GEMINI_MODEL") or "gemini-3-flash-preview"
    logger.info("Using Gemini model: %s", model_name)

    client = _get_client()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=body,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
    except ClientError as e:
        if e.code == 429:
            logger.warning(
                "Gemini API rate limit exceeded (429). "
                "Free tier quota may be exhausted. "
                "Please wait and retry later. Detail: %s",
                e.message,
            )
            raise
        raise

    raw_text = response.text.strip()
    logger.debug("Gemini response: %s", raw_text)

    return _parse_response(raw_text)


def _parse_response(raw_text: str) -> list[ClassifiedItem]:
    """Gemini のレスポンス JSON を ClassifiedItem リストにパースする。"""
    # マークダウンのコードブロック記号を除去
    text = raw_text
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse Gemini response as JSON: %s", raw_text)
        return []

    items = data.get("items", [])
    result = []
    for item in items:
        category = item.get("category", "")
        summary = item.get("summary", "")
        original = item.get("original", "")
        if category in NOTIFY_CATEGORIES and summary:
            result.append(ClassifiedItem(category=Category(category), summary=summary, original=original))

    logger.info("Classified %d relevant item(s)", len(result))
    return result
