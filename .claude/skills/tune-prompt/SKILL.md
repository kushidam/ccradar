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
- 正解データ: `scripts/ground_truth.csv`（`scripts/build_truth.py` で作成）
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
`scripts/eval_result.csv` の分析はサブエージェント内で完結させ、
メインコンテキストには問題サマリのみ返すこと。

`scripts/eval_result.csv` から以下を分析:
- **FN（通知漏れ）**: `notify_match=false` かつ `truth_notify=true` の項目を全件抽出し、原因を特定する（最重要）
  - original テキストのマッチング失敗か、そもそも Gemini が項目を出力しなかったか
- **FP（過検出）**: `notify_match=false` かつ `truth_notify=false` の項目（参考情報）
- カテゴリ不一致: `gemini_category` が `truth_category` と異なる項目（参考情報）

FN の各項目について、リリースノートのパターンを確認する:
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
2. FN（通知漏れ）の件数を前回と比較
3. FN > 0 なら Phase 2 に戻る。FN = 0 なら Phase 5 へ
4. **最大 3 回まで反復** する（API 使用量に配慮）。3 回で FN = 0 に到達しなかった場合も Phase 5 へ進む

### Phase 5: 最終レポート

以下を出力した後、**AskUserQuestion ツールを使用して**ユーザーに最終確認する:

1. **FN/FP 比較テーブル**: 初回 → 最終の FN・FP 件数
2. **SYSTEM_PROMPT の diff**: 変更前後の差分
3. **残存課題**: FN が 0 に到達しなかった場合、該当項目と原因

AskUserQuestion で確認:
- question: "プロンプトの変更を確定しますか？"
- options: "確定する" / "変更を元に戻す" / "さらに反復する"

## 評価指標

「通知すべき項目を通知する」を Positive と定義する。

| 指標 | 定義 | 意味 |
|------|------|------|
| TP | truth=通知対象, gemini=通知した | 正しく通知 |
| TN | truth=非通知, gemini=通知しなかった | 正しく除外 |
| FP | truth=非通知, gemini=通知した | 過検出（Bugfix を通知してしまう等。妥協可） |
| FN | truth=通知対象, gemini=通知しなかった | 通知漏れ（**最重要**） |

### 目標

| 指標 | 目標 | 備考 |
|------|------|------|
| FN（通知漏れ） | 0 件 | 通知すべき項目が消えないこと（唯一のハード目標） |

FP（過検出）は許容する。カテゴリ別検出率・Bugfix除外率・MISS/EXTRA/DIFF/LEAK は参考情報として残すが、目標値からは外す。
