# 正解データ選定基準

## テストすべきパターン

1. **標準動詞** — `Added` / `Fixed` / `Improved` / `Changed` で始まる項目
2. **`[Platform]` 接頭辞** — `[VSCode]`, `[SDK]` 等、角括弧付き
3. **`Platform:` 接頭辞** — `Windows:`, `VSCode:` 等、括弧なしコロン付き
4. **動詞なし Feature/Improvement** — `Simple mode now includes ...`, `SDK model info now includes ...` 等
5. **動詞なし Change** — `Sonnet 4.5 is being removed ...` 等
6. **未知の動詞** — `Blocked`, `Moved`, `Simplified`, `Use`, `Increased` 等
7. **Bugfix-only リリース** — Feature/Improvement/Change が一切なく、空結果を期待するケース
8. **大量項目リリース** — 20 項目以上、見落としテスト用

## 現在の選定

| リリース | 項目数 | カバーするパターン |
|---------|--------|-------------------|
| v2.1.49 | 20 | 標準動詞, 動詞なしF, 動詞なしC |
| v2.1.47 | 68 | 標準動詞, Platform:, 動詞なしF, 未知動詞, 大量 |
| v2.1.45 | 15 | 標準動詞, [Platform] |
| v2.1.44 | 1 | 標準動詞, BugfixOnly |

**4 件で全 8 パターンを網羅。**

### 選定理由

- **v2.1.49**: 動詞なし Change（`Sonnet 4.5 is being removed...`）を持つ唯一のリリース。動詞なし Feature も複数含む
- **v2.1.47**: 68 項目の大量リリース。`Windows:` / `VSCode:` の Platform: 接頭辞、`Moved` / `Simplified` / `Use` / `Increased` 等の未知動詞を含む
- **v2.1.45**: `[VSCode]` の角括弧付きプラットフォーム接頭辞を持つ唯一のリリース
- **v2.1.44**: 1 項目のみの Bugfix-only リリース。分類結果が空になることを検証

### データソース

GitHub Releases API（`gh api repos/anthropics/claude-code/releases`）から取得した Release body を使用。

### 最終更新

2026-02-21 — 直近 15 リリース（v2.1.30〜v2.1.49）を分析して選定
