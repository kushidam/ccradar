#!/usr/bin/env python3
"""プロンプト評価スクリプト。

正解データ（scripts/ground_truth.csv）を基に Gemini 分類プロンプトの精度を評価する。
正解データが未作成の場合は --build-truth で自動生成 → Claude がレビュー → ユーザー承認のフローで作成する。

Usage:
    # 正解データの自動生成（特定バージョン指定）
    uv run python scripts/eval_prompt.py --build-truth --versions 2.1.45,2.1.49,2.1.47,2.1.44

    # 正解データの自動生成（直近 N 件からフォールバック）
    uv run python scripts/eval_prompt.py --build-truth --count N

    # 正解データに含まれるバージョンで評価
    uv run python scripts/eval_prompt.py
"""

import argparse
import csv
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.classifier import classify_release
from src.github_client import fetch_releases, get_release_body, get_release_by_tag, get_release_version

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GROUND_TRUTH_PATH = PROJECT_ROOT / "scripts" / "ground_truth.csv"
EVAL_RESULT_PATH = PROJECT_ROOT / "scripts" / "eval_result.json"

# 先頭動詞 → 正解カテゴリのマッピング
VERB_TO_CATEGORY = {
    "added": "Feature",
    "fixed": "Bugfix",
    "improved": "Improvement",
    "changed": "Change",
    "removed": "Change",
    "deprecated": "Change",
    "breaking": "Breaking",
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
    """先頭動詞ベースで正解データの草案を生成し CSV に保存する。

    Unknown 項目は Claude がレビュー・補完する前提。
    """
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
    print(f"\n次のステップ: Claude が Unknown 項目をレビューしてカテゴリを補完します。")


def load_ground_truth() -> dict[str, list[dict]]:
    """保存済みの正解データ（CSV）を読み込み、バージョンごとにグループ化して返す。"""
    if not GROUND_TRUTH_PATH.exists():
        print(f"正解データが見つかりません: {GROUND_TRUTH_PATH}")
        print("先に --build-truth で正解データを作成してください。")
        sys.exit(1)

    versions: dict[str, list[dict]] = {}
    with open(GROUND_TRUTH_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ver = row["version"]
            if ver not in versions:
                versions[ver] = []
            versions[ver].append({"text": row["text"], "category": row["category"]})

    return versions


def evaluate(count: int) -> dict:
    """正解データに含まれるバージョンを対象に Gemini 分類プロンプトの精度を評価する。"""

    # 正解データ読み込み
    ground_truth = load_ground_truth()
    target_versions = list(ground_truth.keys())

    print("=" * 70)
    print(f"Fetching {len(target_versions)} releases from ground truth: {', '.join(target_versions)} ...")
    releases = fetch_releases_by_versions(target_versions)
    print(f"Fetched {len(releases)} releases")

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    all_results = []

    # カテゴリ別の集計
    agg = {
        "Feature": {"expected": 0, "actual": 0},
        "Improvement": {"expected": 0, "actual": 0},
        "Change": {"expected": 0, "actual": 0},
        "Breaking": {"expected": 0, "actual": 0},
        "Bugfix": {"total": 0, "leaked": 0},
    }

    for release in releases:
        version = get_release_version(release)
        body = get_release_body(release)

        if not body or not body.strip():
            continue

        # 正解データ取得
        truth_items = ground_truth[version]

        truth_by_cat = defaultdict(list)
        for t in truth_items:
            if t["category"] != "Unknown":
                truth_by_cat[t["category"]].append(t["text"])

        # Gemini 分類
        items = classify_release(body)
        gemini_by_cat = defaultdict(list)
        for item in items:
            gemini_by_cat[item.category].append(item.summary)

        # 集計
        for cat in ["Feature", "Improvement", "Change", "Breaking"]:
            expected = len(truth_by_cat.get(cat, []))
            actual = len(gemini_by_cat.get(cat, []))
            agg[cat]["expected"] += expected
            agg[cat]["actual"] += actual

        agg["Bugfix"]["total"] += len(truth_by_cat.get("Bugfix", []))
        agg["Bugfix"]["leaked"] += len(gemini_by_cat.get("Bugfix", []))

        # Issue 検出
        issues = []
        for cat in ["Feature", "Improvement", "Change", "Breaking"]:
            expected = len(truth_by_cat.get(cat, []))
            actual = len(gemini_by_cat.get(cat, []))
            if expected > 0 and actual == 0:
                issues.append(f"MISS: {cat} {expected}件が未検出")
            elif expected == 0 and actual > 0:
                issues.append(f"EXTRA: {cat} {actual}件を誤検出")
            elif abs(expected - actual) > 1:
                issues.append(f"DIFF: {cat} 正解{expected}件 vs Gemini{actual}件")

        bugfix_leaked = len(gemini_by_cat.get("Bugfix", []))
        if bugfix_leaked > 0:
            issues.append(f"LEAK: Bugfix {bugfix_leaked}件が漏れ（除外されるべき）")

        result = {
            "version": version,
            "truth_counts": {cat: len(entries) for cat, entries in truth_by_cat.items()},
            "gemini_counts": {cat: len(entries) for cat, entries in gemini_by_cat.items()},
            "truth_items": dict(truth_by_cat),
            "gemini_items": dict(gemini_by_cat),
            "issues": issues,
        }
        all_results.append(result)

        # バージョンごとの出力
        print(f"\n--- {version} ---")
        truth_summary = {k: len(v) for k, v in truth_by_cat.items()}
        gemini_summary = {k: len(v) for k, v in gemini_by_cat.items()}
        print(f"  正解: {truth_summary}")
        print(f"  Gemini: {gemini_summary}")
        if issues:
            for issue in issues:
                print(f"  ⚠ {issue}")
        else:
            print("  ✓ OK")

        for item in items:
            print(f"    [{item.category}] {item.summary}")

    # サマリー
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"評価バージョン数: {len(all_results)}")

    for cat in ["Feature", "Improvement", "Change", "Breaking"]:
        expected = agg[cat]["expected"]
        actual = agg[cat]["actual"]
        if expected > 0:
            ratio = actual / expected * 100
            print(f"  {cat}: 正解 {expected}件 → Gemini {actual}件 (検出率 {ratio:.0f}%)")
        else:
            print(f"  {cat}: 正解 0件 → Gemini {actual}件")

    bugfix_total = agg["Bugfix"]["total"]
    bugfix_leaked = agg["Bugfix"]["leaked"]
    if bugfix_total > 0:
        exclude_rate = (bugfix_total - bugfix_leaked) / bugfix_total * 100
        print(
            f"  Bugfix除外率: {exclude_rate:.0f}% "
            f"(除外{bugfix_total - bugfix_leaked}/{bugfix_total}件, 漏れ{bugfix_leaked}件)"
        )

    issue_count = sum(1 for r in all_results if r["issues"])
    print(f"\n問題のあるバージョン: {issue_count} / {len(all_results)}")

    # JSON 保存
    output_data = {
        "total_versions": len(all_results),
        "aggregate": {k: dict(v) for k, v in agg.items()},
        "results": all_results,
    }

    with open(EVAL_RESULT_PATH, "w") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    print(f"\n詳細結果: {EVAL_RESULT_PATH}")

    return output_data


def main():
    parser = argparse.ArgumentParser(description="プロンプト評価スクリプト")
    parser.add_argument(
        "--count",
        type=int,
        default=20,
        help="--build-truth 時のフォールバック: 直近 N 件から生成（デフォルト: 20）",
    )
    parser.add_argument(
        "--versions",
        type=str,
        default=None,
        help="--build-truth 時: カンマ区切りのバージョン指定（例: 2.1.45,2.1.49,2.1.47,2.1.44）",
    )
    parser.add_argument(
        "--build-truth",
        action="store_true",
        help="正解データの草案を自動生成する（先頭動詞ベース、要レビュー）",
    )
    args = parser.parse_args()

    if args.build_truth:
        version_list = [v.strip() for v in args.versions.split(",")] if args.versions else None
        build_truth(args.count, version_list)
    else:
        evaluate(args.count)


if __name__ == "__main__":
    main()
