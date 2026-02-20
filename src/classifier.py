"""Gemini API を使用した LLM ベースの分類・要約モジュール。"""

import logging
import os
from dataclasses import dataclass

from google import genai
from google.genai import types

from src.categories import NOTIFY_CATEGORIES, Category

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたはCLIツール「Claude Code」のリリースノートを分析するアシスタントです。

## 入力形式

入力はマークダウン形式のリリースノートです。各項目は `- ` で始まる箇条書きです。
項目には [VSCode], [SDK], [Windows], [IDE], [Bedrock] 等のプラットフォームプレフィックスが付く場合があります。
項目の書き出しは "Added", "Fixed", "Improved" 等の動詞で始まるとは限りません。
内容の意味に基づいて分類してください。

## 分類カテゴリ

各項目を以下のカテゴリに分類してください:
- Feature: 新機能・新コマンド・新設定の追加（例: 新しいフラグ、新しいキーバインド、新しいツール）
- Improvement: 既存機能の拡張・パフォーマンス改善・UX改善（例: 起動高速化、メモリ使用量削減、UI改善）
- Bugfix: バグ修正・クラッシュ修正（例: "Fixed ..." で始まる項目の大半）
- Change: 動作変更・非推奨化・削除・デフォルト値変更（例: モデルの入れ替え、設定の移動）
- Breaking: 破壊的変更・後方互換性のない変更

## 抽出ルール

- Feature, Improvement, Breaking, Change に該当する項目のみを抽出してください
- Bugfix は原則スキップしてください。ただしセキュリティ修正は Change として含めてください
- プラットフォーム固有の項目（[VSCode] 等）も対象に含めてください

## 出力形式

以下のJSON形式で返してください（マークダウンのコードブロックは不要）:
{
  "items": [
    {
      "category": "Feature" または "Improvement" または "Breaking" または "Change",
      "summary": "日本語での要約（1〜2文）",
      "original": "元の箇条書きテキスト（先頭の '- ' を除いた原文そのまま）"
    }
  ]
}

該当する項目がない場合は空のリストを返してください:
{"items": []}
"""


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

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.0-flash")
    logger.info("Using Gemini model: %s", model_name)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=body,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    raw_text = response.text.strip()
    logger.debug("Gemini response: %s", raw_text)

    return _parse_response(raw_text)


def _parse_response(raw_text: str) -> list[ClassifiedItem]:
    """Gemini のレスポンス JSON を ClassifiedItem リストにパースする。"""
    import json

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
