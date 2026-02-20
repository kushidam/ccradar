# 正解データ選定基準

## パターン一覧

プロンプト評価用の正解データは、以下のパターンを網羅するよう選定する:

1. **標準動詞** — Added / Fixed / Improved / Changed / Removed / Deprecated
2. **[Platform] 接頭辞** — `[VSCode]`, `[SDK]` 等の角括弧付き
3. **Platform: 接頭辞** — `Windows:`, `VSCode:` 等のコロン付き（括弧なし）
4. **動詞なし Feature/Improvement** — 主語で始まる新機能・改善（`Simple mode now includes ...`）
5. **動詞なし Change** — 主語で始まる変更・削除（`Sonnet 4.5 is being removed ...`）
6. **未知の動詞** — 標準動詞以外（`Simplified ...`, `Moved ...`, `Use ...`, `Increased ...`）
7. **Bugfix-only リリース** — Fixed のみで構成（空結果を期待）
8. **大量項目リリース** — 30 件以上（見落としテスト用）

## 現在の選定

**選定日**: 2026-02-21
**選定数**: 4 リリース / 104 項目

| リリース | Items | カバーするパターン |
|---------|-------|-------------------|
| v2.1.47 | 68 | 標準動詞, Platform:, 動詞なしF, 未知動詞, 大量 |
| v2.1.49 | 20 | 標準動詞, 動詞なしF, 動詞なしC |
| v2.1.45 | 15 | 標準動詞, [Platform] |
| v2.1.44 | 1 | BugfixOnly |

### パターンカバレッジ

| パターン | カバー元 |
|---------|---------|
| 標準動詞 | v2.1.47, v2.1.49, v2.1.45 |
| [Platform] | v2.1.45 (`[VSCode] Improved ...`) |
| Platform: | v2.1.47 (`Windows:`, `VSCode:`) |
| 動詞なし Feature/Improvement | v2.1.49 (`Simple mode ...`, `SDK model info ...`), v2.1.47 (`Search patterns ...`) |
| 動詞なし Change | v2.1.49 (`Sonnet 4.5 ... is being removed`) |
| 未知の動詞 | v2.1.47 (`Simplified`, `Use`, `Moved`, `Increased`) |
| Bugfix-only | v2.1.44 (Fixed 1 件のみ) |
| 大量項目 | v2.1.47 (68 件) |
