---
description: 正解データ用リリースを選定・構築する
user_invocable: true
argument_description: 候補として取得するリリース数（デフォルト: 15）
allowed-tools:
  - AskUserQuestion
  - Bash(gh:*)
  - Bash(uv run python:*)
  - Read
  - Write
  - Edit
  - Glob
  - Task
---

# 正解データ選定スキル

プロンプト評価に使う正解データ（`scripts/ground_truth.json`）を、
パターンのバリエーション基準で選定・構築する。
$ARGUMENTS に候補取得件数が指定されていれば使用し、未指定時は 15 件。

**重要: データソースは GitHub Releases API に統一すること。**
正解データの項目数・内容は `gh api` で取得したリリースノートに基づくこと。

## 選定基準

`docs/ground-truth-selection.md` に記載のパターンを網羅すること:

1. 標準動詞（Added / Fixed / Improved / Changed）
2. `[Platform]` 接頭辞（`[VSCode]`, `[SDK]` 等）
3. `Platform:` 接頭辞・括弧なし（`Windows:`, `VSCode:` 等）
4. 動詞なし Feature/Improvement（`Simple mode now includes ...`）
5. 動詞なし Change（`Sonnet 4.5 is being removed ...`）
6. 未知の動詞（`Blocked ...`, `Moved ...`, `Simplified ...`）
7. Bugfix-only リリース（空結果を期待するケース）
8. 大量項目リリース（見落としテスト用）

## ワークフロー

### Step 1: 候補リリースの取得

```bash
gh api repos/anthropics/claude-code/releases --jq '.[0:{件数}][] | "=== \(.tag_name) (\(.body | split("\n") | map(select(startswith("- "))) | length) items) ===\n\(.body)\n"'
```

### Step 2: パターン分析

**リリース単位で Task ツール（subagent_type=Explore）を並列起動する。**
Step 1 で取得した各リリースにつき 1 エージェントを起動し、
そのリリースのパターン出現状況（✓/空のリスト）だけを返させる。
全エージェントの結果を受け取ったら、自身でマトリクス表に集約する。

**注意: スクリプトやコードを生成してはならない。**
パターン分析はリリースノートのテキストを読んで判断するだけで十分である。

各リリースの項目をスキャンして、上記パターンの出現状況をマトリクスで表示:

```
           | 標準動詞 | [Platform] | Platform: | 動詞なしF | 動詞なしC | 未知動詞 | BugfixOnly | 大量 |
v2.1.49    |    ✓    |           |           |     ✓    |    ✓     |         |           |      |
v2.1.47    |    ✓    |           |     ✓     |          |          |    ✓    |           |  ✓   |
...
```

### Step 3: 最小セット選定

3〜5 件で全パターンを網羅するリリースの組み合わせを提案する。
選定理由を簡潔に説明する。

### Step 4: ユーザー確認

**AskUserQuestion ツールを使用して**、選定したリリースの承認を得る。

例:
- question: "以下のリリースを正解データに使用してよいですか？\n- v2.1.47 (大量項目、未知動詞)\n- v2.1.49 (標準動詞、動詞なし)\n- ..."
- options: "この組み合わせで進める" / "候補を変更したい"

### Step 5: 正解データ構築

承認されたリリースに対して:

1. 各項目を先頭動詞で仮分類:
   ```bash
   uv run python scripts/eval_prompt.py --build-truth --versions {v1},{v2},{v3},{v4}
   ```

2. Unknown 項目をレビューして適切なカテゴリを付与:
   - CHANGELOG.md の該当バージョンの文脈を参照
   - 各 Unknown 項目に Feature / Improvement / Change / Bugfix / Breaking を割り当て
   - 自動分類の誤りも修正

3. 修正案をバージョンごとに一覧表示し、**AskUserQuestion ツールを使用して**ユーザーに確認する。
   各バージョンについて、変更した項目のカテゴリ割り当てが正しいか承認を得る。

4. 承認後 `scripts/ground_truth.json` を保存

### Step 6: ドキュメント更新

`docs/ground-truth-selection.md` の「現在の選定」セクションを更新する。
