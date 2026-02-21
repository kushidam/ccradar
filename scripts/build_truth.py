#!/usr/bin/env python3
"""正解データ草案の生成スクリプト。

GitHub からリリースを取得し、先頭動詞ヒューリスティックで仮分類して CSV に保存する。
Unknown 項目は人または AI がレビュー・補完する前提。

Usage:
    # 特定バージョン指定
    uv run python scripts/build_truth.py --versions 2.1.45,2.1.49,2.1.47,2.1.44

    # 直近 N 件から生成
    uv run python scripts/build_truth.py --count 20
"""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.categories import Category
from src.github_client import fetch_releases, get_release_body, get_release_by_tag, get_release_version

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GROUND_TRUTH_PATH = PROJECT_ROOT / "scripts" / "ground_truth.csv"

# 先頭動詞 → 正解カテゴリのマッピング
VERB_TO_CATEGORY = {
    "added": Category.FEATURE,
    "fixed": Category.BUGFIX,
    "improved": Category.IMPROVEMENT,
    "changed": Category.CHANGE,
    "removed": Category.CHANGE,
    "deprecated": Category.CHANGE,
    "breaking": Category.BREAKING,
}


def extract_items_from_body(body: str) -> list[dict]:
    """リリースボディから箇条書き項目を抽出し、先頭動詞で仮分類する。

    Returns:
        [{"text": "原文", "category": "Feature"|...|"Unknown"}, ...]
    """
    items = []
    for line in body.split("\n"):
        m = re.match(r"^- (.+)", line)
        if not m:
            continue
        text = m.group(1).strip()

        # プラットフォームプレフィックス（[VSCode] 等）を除去して動詞を取得
        clean = re.sub(r"^\[.*?\]\s*", "", text)
        first_word = clean.split()[0].lower().rstrip(":") if clean else ""
        category = VERB_TO_CATEGORY.get(first_word, "Unknown")

        items.append({"text": text, "category": category})

    return items


def fetch_releases_by_versions(version_list: list[str]) -> list[dict]:
    """指定バージョンのリリースを個別に取得する。"""
    releases = []
    for ver in version_list:
        release = get_release_by_tag(ver)
        if release:
            releases.append(release)
        else:
            logger.warning("Release not found: %s", ver)
    return releases


def build_truth(count: int, version_list: list[str] | None = None) -> None:
    """先頭動詞ベースで正解データの草案を生成し CSV に保存する。"""
    print("=" * 70)

    if version_list:
        print(f"Building ground truth draft for versions: {', '.join(version_list)} ...")
        releases = fetch_releases_by_versions(version_list)
    else:
        print(f"Building ground truth draft from latest {count} releases ...")
        releases = fetch_releases(per_page=count)

    print(f"Fetched {len(releases)} releases")

    rows = []
    unknown_count = 0

    for release in releases:
        version = get_release_version(release)
        body = get_release_body(release)
        if not body or not body.strip():
            continue

        items = extract_items_from_body(body)
        for item in items:
            rows.append({"version": version, "category": item["category"], "text": item["text"]})
            if item["category"] == "Unknown":
                unknown_count += 1

    with open(GROUND_TRUTH_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["version", "category", "text"])
        writer.writeheader()
        writer.writerows(rows)

    total_count = len(rows)
    print(f"\n正解データ草案を保存: {GROUND_TRUTH_PATH}")
    print(f"  総項目数: {total_count}")
    print(f"  自動分類: {total_count - unknown_count}件")
    print(f"  Unknown（要レビュー）: {unknown_count}件")
    print(f"\n次のステップ: 人またはAI が Unknown 項目をレビューしてカテゴリを補完します。")


def main():
    parser = argparse.ArgumentParser(description="正解データ草案の生成")
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="直近 N 件から生成（デフォルト: 20）",
    )
    parser.add_argument(
        "--versions",
        type=str,
        default=None,
        help="カンマ区切りのバージョン指定（例: 2.1.45,2.1.49,2.1.47,2.1.44）",
    )
    args = parser.parse_args()

    version_list = [v.strip() for v in args.versions.split(",")] if args.versions else None
    build_truth(args.count, version_list)


if __name__ == "__main__":
    main()
