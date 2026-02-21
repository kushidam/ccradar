# CLAUDE.md

## プロジェクト概要

Claude Code Release Radar — Claude Code のリリースから新機能・機能拡張を抽出し Slack 通知する Python システム。

## 技術スタック

- Python 3.12
- Gemini API（google-genai）— リリースノートの分類・要約
- GitHub REST API（requests）— リリース情報の取得
- Slack Incoming Webhook — 通知送信
- GitHub Actions — 定期実行（毎日 9:00 JST）

## ディレクトリ構成

```
src/
  main.py           # エントリーポイント
  github_client.py  # GitHub API クライアント
  classifier.py     # Gemini による分類・要約
  prompts.py        # Gemini API 用システムプロンプト
  notifier.py       # Slack 通知
  state.py          # 処理済みバージョン管理（data/state.json）
scripts/
  build_truth.py    # 正解データ草案の生成
  eval_prompt.py    # 分類精度の評価
  ground_truth.csv # 評価用の正解データ
data/
  state.json        # 状態ファイル（Git 管理、Actions が自動コミット）
docs/               # 要件定義書・設計ドキュメント
.github/workflows/
  release-radar.yml
```

## コマンド

```bash
# 依存インストール（仮想環境作成 + パッケージインストール）
uv sync

# 環境変数の設定（初回のみ）
cp .env.example .env && vi .env

# dry-run（Slack 送信なし、state.json 更新なし）
uv run python -m src.main --dry-run

# 特定バージョンのみ処理（検証用）
uv run python -m src.main --dry-run --version 2.1.47

# 本番実行
uv run python -m src.main

# プロンプト評価（正解データに対する分類精度を測定）
uv run python scripts/eval_prompt.py

# 正解データの草案生成（特定バージョン指定）
uv run python scripts/build_truth.py --versions 2.1.45,2.1.49,2.1.47,2.1.44

# 正解データの草案生成（直近 N 件から）
uv run python scripts/build_truth.py --count 20
```

**注意**: `python src/main.py` ではなく `python -m src.main` で実行すること（インポート解決のため）。

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| GEMINI_API_KEY | Yes | Gemini API キー |
| SLACK_WEBHOOK_URL | Yes（dry-run 時は不要） | Slack Webhook URL |
| GEMINI_MODEL | No | モデル名（デフォルト: gemini-3-flash-preview） |
| GITHUB_TOKEN | No | GitHub API トークン（レート制限緩和用、Actions では自動提供） |

## データソース

- **バージョン検出**: GitHub Releases API（タグベース）
- **分類対象の本文**: CHANGELOG.md を優先し、取得失敗時は Release body にフォールバック
- **既知の制約**: CHANGELOG.md にのみ存在し Release タグが未作成のバージョンは検出・通知の対象外

## コーディング規約

- コメント・docstring は日本語で記述する
- ログメッセージは英語（logging モジュール使用）
- シンプルさ重視、過度な抽象化は避ける

