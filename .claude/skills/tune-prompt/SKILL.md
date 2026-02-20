---
description: Gemini 分類プロンプトを自動評価・最適化する
user_invocable: true
argument_description: 引数なし。正解データ（ground_truth.csv）のバージョンで評価する
allowed-tools:
  - AskUserQuestion
  - Bash(uv run python:*)
  - Read
  - Edit
  - Glob
  - Task
---

# プロンプト調整スキル

`src/classifier.py` の `SYSTEM_PROMPT` を反復的に最適化する。
評価対象は `scripts/ground_truth.csv` に含まれるバージョン。

## 前提

- 評価スクリプト: `scripts/eval_prompt.py`
- 正解データ: `scripts/ground_truth.csv`（`/build-truth` で作成）
- 選定基準: `docs/ground-truth-selection.md`

## ワークフロー

### Phase 0: 正解データの確認

`scripts/ground_truth.csv` が存在しない場合:
- **AskUserQuestion ツールを使用して**ユーザーに案内する:
  - question: "正解データ（ground_truth.csv）が見つかりません。先に作成しますか？"
  - options: "/build-truth を実行する" / "中止する"

存在する場合:
- 含まれるバージョンと Unknown 項目の有無を確認
- Unknown が残っている場合は **AskUserQuestion ツールを使用して**ユーザーに警告し、続行するか確認する

### Phase 1: 現状評価

1. 現在の `SYSTEM_PROMPT` を `src/classifier.py` から読み取り記録する（Before）
2. 評価スクリプトを実行:
   ```bash
   uv run python scripts/eval_prompt.py
   ```
   正解データのバージョンのみ自動で評価される。
3. `scripts/eval_result.csv` を読み込み、初回スコアを記録する

### Phase 2: 問題分析

**Task ツール（subagent_type=Explore）でサブエージェントに委譲する。**
eval 結果とリリースノート生テキストの突き合わせはサブエージェント内で完結させ、
メインコンテキストには問題タイプ別サマリのみ返すこと。

`scripts/eval_result.csv` から以下を分析:
- **通知漏れ**: truth_notify=true だが gemini_notify=false（最重要）
- **過検出**: truth_notify=false だが gemini_notify=true
- **MISS**: 正解カテゴリの項目を Gemini が 0 件返した（見落とし）
- **EXTRA**: 正解にないカテゴリを Gemini が誤検出した
- **DIFF**: カテゴリ件数が正解と大きく乖離している
- **LEAK**: 除外すべき Bugfix 項目が Gemini 出力に含まれている

リリースノートの実際のパターンも確認する:
- 先頭動詞パターン: `Added ...`, `Fixed ...`, `Improved ...`
- プラットフォームプレフィックス: `[VSCode] Added ...`
- 動詞なしパターン: `Simple mode now includes ...`, `Sonnet 4.5 is being removed ...`

### Phase 3: プロンプト改善

`src/classifier.py` の `SYSTEM_PROMPT` を修正する。典型的な改善ポイント:
- 分類基準の明確化・具体例の追加
- 先頭動詞がない項目の分類ガイダンス追加
- Bugfix 除外ルールの強化
- 出力 JSON フォーマットの安定化

### Phase 4: 再評価（自動反復）

1. 再度評価スクリプトを実行
2. 前回のスコアと比較
3. 改善が見られれば Phase 2 に戻る
4. **最大 3 回まで反復** する（API 使用量に配慮）

### Phase 5: 最終レポート

以下を出力した後、**AskUserQuestion ツールを使用して**ユーザーに最終確認する:

1. **精度比較テーブル**: 初回 → 最終の各カテゴリ検出率
2. **SYSTEM_PROMPT の diff**: 変更前後の差分
3. **残存課題**: 改善しきれなかった問題点（あれば）

AskUserQuestion で確認:
- question: "プロンプトの変更を確定しますか？"
- options: "確定する" / "変更を元に戻す" / "さらに反復する"

## 評価目標

| 指標 | 目標 | 備考 |
|------|------|------|
| 通知漏れ | 0 件 | 通知すべき項目が消えないこと（唯一のハード目標） |

カテゴリ別検出率・Bugfix除外率・MISS/EXTRA/DIFF/LEAK は参考情報として残すが、目標値からは外す。
