# 正解データの選定基準

## 概要

プロンプト評価に使う正解データは「直近 N 件」ではなく、**パターンのバリエーション**を基準にリリースを選定する。
3〜5 件のリリースで以下のパターンを網羅することを目標とする。

## カバーすべきパターン

| # | パターン | 例 | 重要度 |
|---|----------|-----|--------|
| 1 | 標準動詞 | `Added ...`, `Fixed ...`, `Improved ...` | 必須 |
| 2 | `[Platform]` 接頭辞 | `[VSCode] Improved ...`, `[SDK] Added ...` | 必須 |
| 3 | `Platform:` 接頭辞（括弧なし） | `Windows: Fixed ...`, `VSCode: Fixed ...` | 必須 |
| 4 | 動詞なし（Feature/Improvement 系） | `Simple mode now includes ...` | 必須 |
| 5 | 動詞なし（Change 系） | `Sonnet 4.5 is being removed ...` | 必須 |
| 6 | 未知の動詞 | `Blocked writes to ...`, `Moved config ...` | 重要 |
| 7 | Bugfix-only リリース | Fixed のみのリリース → 空を返すべき | 重要 |
| 8 | 大量項目リリース | 68 件等 → 見落としが起きやすい | あると良い |

## 現在の選定（2026-02 時点）

| リリース | 項目数 | カバーするパターン |
|----------|--------|-------------------|
| v2.1.45 | 15 件 | #1 基本形（Added/Fixed/Improved） + #2 `[VSCode]` 接頭辞 |
| v2.1.49 | 20 件 | #1 標準動詞 + #4 動詞なし Feature + #5 動詞なし Change |
| v2.1.47 | 68 件 | #1 標準動詞、#3 `Windows:`/`VSCode:` 接頭辞、#4 動詞なし Feature、#5 動詞なし Change、#6 未知動詞、#8 大量項目 |
| v2.1.44 | 1 件 | #7 Bugfix-only リリース（空結果を期待） |

### 選定理由

- **v2.1.45**: 最も標準的な構成。Added 4 件、Fixed 7 件、Improved 3 件、`[VSCode]` 1 件とバランスが良い
- **v2.1.49**: `Simple mode now includes...`（動詞なし Feature）、`Sonnet 4.5 is being removed...`（動詞なし Change）等の動詞なしパターンの代表例を含む。v2.1.47 と重複するが、クリーンな動詞なし例として評価精度向上に貢献
- **v2.1.47**: 68 件の大型リリース。`Windows: Fixed...`/`VSCode: Fixed...` 等の括弧なしプラットフォーム接頭辞、`Moved...`/`Simplified...`/`Increased...` 等の未知動詞、`Use ctrl+f to...`（Change）等の多様なパターンを含む
- **v2.1.44**: `Fixed auth refresh errors` の 1 件のみ。Bugfix-only リリースで空結果を返すべきケース

## 更新タイミング

以下の場合に `/select-ground-truth` スキルで正解データを再選定する:

- リリースノートのフォーマットが変わった
- 新しいプラットフォーム接頭辞（例: `[Bedrock]`）が頻出するようになった
- メジャーバージョンが変わった（v3.x.x 等）
- 既存の正解データで評価精度が頭打ちになった
