#!/usr/bin/env python3
"""プロンプト評価スクリプト。

正解データ（scripts/ground_truth.csv）を基に Gemini 分類プロンプトの精度を評価する。
正解データが未作成の場合は build_truth.py で先に作成すること。

Usage:
    uv run python scripts/eval_prompt.py
"""

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from src.categories import NOTIFY_CATEGORIES, Category
from src.classifier import classify_release

GROUND_TRUTH_PATH = PROJECT_ROOT / "scripts" / "ground_truth.csv"
_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
EVAL_RESULT_PATH = PROJECT_ROOT / "scripts" / f"eval_result_{_timestamp}.csv"


def load_ground_truth() -> dict[str, list[dict]]:
    """保存済みの正解データ（CSV）を読み込み、バージョンごとにグループ化して返す。"""
    if not GROUND_TRUTH_PATH.exists():
        print(f"正解データが見つかりません: {GROUND_TRUTH_PATH}")
        print("先に build_truth.py で正解データを作成してください。")
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


def reconstruct_body(items: list[dict]) -> str:
    """正解データの text 列からリリース本文を再構成する。"""
    return "\n".join(f"- {item['text']}" for item in items)


def _normalize(text: str) -> str:
    """マッチング用にテキストを正規化する。"""
    text = unicodedata.normalize("NFKC", text)
    text = text.strip()
    # 括弧内の issue 参照等を除去して比較しやすくする
    text = re.sub(r"\s*\(anthropics/claude-code#\d+\)\s*", "", text)
    # 連続空白を1つに
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def match_gemini_to_truth(
    truth_items: list[dict],
    gemini_items: list,
) -> list[dict]:
    """正解データと Gemini 出力を項目レベルでマッチングする。

    Returns:
        正解データの各項目に Gemini の結果を付与したリスト。
    """
    # Gemini 出力の original を正規化してインデックス化
    gemini_by_norm: dict[str, list] = defaultdict(list)
    for item in gemini_items:
        norm = _normalize(item.original)
        gemini_by_norm[norm].append(item)

    matched_results = []
    used_gemini = set()  # 使用済み Gemini 項目のインデックス

    for truth in truth_items:
        truth_norm = _normalize(truth["text"])
        truth_category = truth["category"]
        truth_notify = truth_category in NOTIFY_CATEGORIES

        gemini_category = ""
        gemini_notify = False
        matched = False

        # 完全一致（正規化後）
        for gi in gemini_by_norm.get(truth_norm, []):
            gi_id = id(gi)
            if gi_id not in used_gemini:
                gemini_category = gi.category
                gemini_notify = True  # Gemini 出力に含まれている = 通知対象
                used_gemini.add(gi_id)
                matched = True
                break

        # 部分一致フォールバック（containment）
        if not matched:
            for norm_key, gi_list in gemini_by_norm.items():
                for gi in gi_list:
                    gi_id = id(gi)
                    if gi_id in used_gemini:
                        continue
                    if truth_norm in norm_key or norm_key in truth_norm:
                        gemini_category = gi.category
                        gemini_notify = True
                        used_gemini.add(gi_id)
                        matched = True
                        break
                if matched:
                    break

        matched_results.append({
            "truth_text": truth["text"],
            "truth_category": truth_category,
            "truth_notify": truth_notify,
            "gemini_category": gemini_category,
            "gemini_notify": gemini_notify,
            "notify_match": truth_notify == gemini_notify,
        })

    return matched_results


def evaluate() -> None:
    """正解データに含まれるバージョンを対象に Gemini 分類プロンプトの精度を評価する。"""

    # 正解データ読み込み
    ground_truth = load_ground_truth()
    target_versions = list(ground_truth.keys())

    print("=" * 70)
    print(f"Evaluating {len(target_versions)} versions from ground truth: {', '.join(target_versions)}")
    print("(GitHub API 不使用 — 正解データからリリース本文を再構成)")

    print("\n" + "=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)

    # カテゴリ別の集計
    agg = {
        Category.FEATURE: {"expected": 0, "actual": 0},
        Category.IMPROVEMENT: {"expected": 0, "actual": 0},
        Category.CHANGE: {"expected": 0, "actual": 0},
        Category.BREAKING: {"expected": 0, "actual": 0},
        Category.BUGFIX: {"total": 0, "leaked": 0},
    }

    # 通知可否の集計
    notify_agg = {
        "truth_notify": 0,
        "gemini_notify": 0,
        "miss": 0,  # 通知漏れ（truth=通知対象 だが gemini=非通知）
        "over": 0,  # 過検出（truth=非通知 だが gemini=通知対象）
    }

    all_csv_rows = []

    for version in target_versions:
        truth_items = ground_truth[version]

        # 正解データからリリース本文を再構成
        body = reconstruct_body(truth_items)

        # 正解カテゴリ別集計
        truth_by_cat = defaultdict(list)
        for t in truth_items:
            if t["category"] != "Unknown":
                truth_by_cat[t["category"]].append(t["text"])

        # Gemini 分類
        items = classify_release(body)
        gemini_by_cat = defaultdict(list)
        for item in items:
            gemini_by_cat[item.category].append(item.summary)

        # カテゴリ別集計
        for cat in NOTIFY_CATEGORIES:
            expected = len(truth_by_cat.get(cat, []))
            actual = len(gemini_by_cat.get(cat, []))
            agg[cat]["expected"] += expected
            agg[cat]["actual"] += actual

        agg[Category.BUGFIX]["total"] += len(truth_by_cat.get(Category.BUGFIX, []))
        agg[Category.BUGFIX]["leaked"] += len(gemini_by_cat.get(Category.BUGFIX, []))

        # 項目レベルのマッチング
        matched = match_gemini_to_truth(truth_items, items)

        for row in matched:
            if row["truth_notify"]:
                notify_agg["truth_notify"] += 1
            if row["gemini_notify"]:
                notify_agg["gemini_notify"] += 1
            if row["truth_notify"] and not row["gemini_notify"]:
                notify_agg["miss"] += 1
            if not row["truth_notify"] and row["gemini_notify"]:
                notify_agg["over"] += 1

            all_csv_rows.append({
                "version": version,
                "text": row["truth_text"],
                "truth_category": row["truth_category"],
                "truth_notify": str(row["truth_notify"]).lower(),
                "gemini_category": row["gemini_category"],
                "gemini_notify": str(row["gemini_notify"]).lower(),
                "notify_match": str(row["notify_match"]).lower(),
            })

        # Issue 検出
        issues = []
        for cat in NOTIFY_CATEGORIES:
            expected = len(truth_by_cat.get(cat, []))
            actual = len(gemini_by_cat.get(cat, []))
            if expected > 0 and actual == 0:
                issues.append(f"MISS: {cat} {expected}件が未検出")
            elif expected == 0 and actual > 0:
                issues.append(f"EXTRA: {cat} {actual}件を誤検出")
            elif abs(expected - actual) > 1:
                issues.append(f"DIFF: {cat} 正解{expected}件 vs Gemini{actual}件")

        bugfix_leaked = len(gemini_by_cat.get(Category.BUGFIX, []))
        if bugfix_leaked > 0:
            issues.append(f"LEAK: Bugfix {bugfix_leaked}件が漏れ（除外されるべき）")

        # 通知漏れ・過検出
        ver_miss = sum(1 for r in matched if r["truth_notify"] and not r["gemini_notify"])
        ver_over = sum(1 for r in matched if not r["truth_notify"] and r["gemini_notify"])
        if ver_miss > 0:
            issues.append(f"通知漏れ: {ver_miss}件")
        if ver_over > 0:
            issues.append(f"過検出: {ver_over}件")

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

    # CSV 出力
    with open(EVAL_RESULT_PATH, "w", newline="") as f:
        fieldnames = ["version", "text", "truth_category", "truth_notify", "gemini_category", "gemini_notify", "notify_match"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_csv_rows)

    # サマリー
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"評価バージョン数: {len(target_versions)}")

    for cat in NOTIFY_CATEGORIES:
        expected = agg[cat]["expected"]
        actual = agg[cat]["actual"]
        if expected > 0:
            ratio = actual / expected * 100
            print(f"  {cat}: 正解 {expected}件 → Gemini {actual}件 (検出率 {ratio:.0f}%)")
        else:
            print(f"  {cat}: 正解 0件 → Gemini {actual}件")

    bugfix_total = agg[Category.BUGFIX]["total"]
    bugfix_leaked = agg[Category.BUGFIX]["leaked"]
    if bugfix_total > 0:
        exclude_rate = (bugfix_total - bugfix_leaked) / bugfix_total * 100
        print(
            f"  Bugfix除外率: {exclude_rate:.0f}% "
            f"(除外{bugfix_total - bugfix_leaked}/{bugfix_total}件, 漏れ{bugfix_leaked}件)"
        )

    # 通知可否サマリー
    print(f"\n  --- 通知可否 ---")
    print(f"  通知対象: 正解 {notify_agg['truth_notify']}件 → Gemini {notify_agg['gemini_notify']}件")
    print(f"  通知漏れ: {notify_agg['miss']}件")
    print(f"  過検出: {notify_agg['over']}件")

    print(f"\n詳細結果: {EVAL_RESULT_PATH}")


def main():
    evaluate()


if __name__ == "__main__":
    main()
