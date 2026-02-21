# Claude Code Release Radar

Claude Code のリリース情報を自動取得し、**新機能・機能拡張・破壊的変更・動作変更**を抽出して Slack に通知する Python システムです。

## 概要

Claude Code は高頻度でアップデートされるため、手動でのキャッチアップが困難です。本システムは GitHub Actions で毎日定期実行され、以下を自動化します:

1. GitHub API から Claude Code の最新リリース情報を取得
2. Gemini API (LLM) でリリースノートを分類・要約
3. Feature / Improvement / Breaking / Change を抽出（Bugfix はスキップ）
4. Slack Incoming Webhook で通知

## 分類カテゴリと通知ルール

Gemini API がリリースノートの各項目を以下のカテゴリに分類します:

| カテゴリ | 説明 | 通知 |
|----------|------|------|
| Feature | 新機能・新コマンド・新設定の追加 | :white_check_mark: |
| Improvement | 既存機能の拡張・パフォーマンス改善・UX改善 | :white_check_mark: |
| Breaking | 破壊的変更・後方互換性のない変更 | :white_check_mark: |
| Change | 動作変更・非推奨化・削除・デフォルト値変更 | :white_check_mark: |
| Bugfix | バグ修正・クラッシュ修正 | :x: スキップ |

- Bugfix は分類対象外（Gemini のプロンプトで除外指示）
- ただしセキュリティ修正は Change として抽出
- Bugfix のみのリリースは簡易テキスト通知（「Bugfix のみ」）

## アーキテクチャ

```
GitHub API (claude-code releases)
        |
        v
  github_client.py    ... リリース情報の取得・差分検知
        |
        v
   classifier.py      ... Gemini API による分類（Feature/Improvement/Breaking/Change）・要約
        |
        v
    notifier.py        ... Slack Incoming Webhook で通知（Feature/Improvement/Breaking/Change）
        |
        v
     state.py          ... 処理済みバージョンの永続化
```

GitHub Actions が毎日 9:00 (JST) にワークフローを実行し、`data/state.json` に処理済みバージョンを記録・自動コミットします。

## セットアップ

### 1. Slack Incoming Webhook の作成

> 📎 [Sending messages using incoming webhooks - Slack](https://api.slack.com/messaging/webhooks)

1. [Slack API: Incoming Webhooks](https://api.slack.com/messaging/webhooks) にアクセス
2. 「Create your Slack app」からアプリを作成（または既存アプリを使用）
3. 「Incoming Webhooks」を有効化
4. 「Add New Webhook to Workspace」で通知先チャンネルを選択
5. 生成された Webhook URL をコピー

### 2. Gemini API キーの取得

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. 「Get API key」からAPIキーを作成
3. 生成された API キーをコピー

### 3. GitHub Environment の設定

> 📎 [Using environments for deployment - GitHub Docs](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)

1. リポジトリの **Settings > Environments** を開く
2. 「**New environment**」をクリックし、名前を `production` にして作成
3. **Deployment branches** で「Selected branches and tags」を選択し、`main` ブランチのみに制限
4. **Environment secrets** に以下を登録:

| Secret 名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得した API キー |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook の URL |

5. （任意）**Environment variables** にモデル名を登録:

| Variable 名 | デフォルト値 | 説明 |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3-flash-preview` | 使用する Gemini モデル |

### 4. 手動実行でテスト

1. GitHub リポジトリの **Actions** タブを開く
2. 左メニューから「**Claude Code Release Radar**」を選択
3. 「**Run workflow**」ボタンをクリック
4. ブランチを確認して「**Run workflow**」を実行
5. Slack チャンネルに通知が届くことを確認

## ローカル実行

パッケージ管理に [uv](https://docs.astral.sh/uv/) を使用しています。

```bash
# 依存関係のインストール（仮想環境作成 + パッケージインストール）
uv sync

# 環境変数の設定（.env.example をコピーして編集）
cp .env.example .env
vi .env  # 実際の API キーを入力

# ドライラン（Slack に通知せず標準出力に表示）
uv run python -m src.main --dry-run

# 特定バージョンのみ処理（検証用）
uv run python -m src.main --dry-run --version 2.1.47

# 実行（Slack に通知）
uv run python -m src.main
```

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API のキー |
| `SLACK_WEBHOOK_URL` | Yes | Slack Incoming Webhook の URL（`--dry-run` 時は不要） |
| `GEMINI_MODEL` | No | 使用する Gemini モデル（デフォルト: `gemini-3-flash-preview`） |

## ディレクトリ構成

```
ccradar/
├── .github/
│   └── workflows/
│       └── release-radar.yml   # GitHub Actions ワークフロー
├── data/
│   └── state.json              # 処理済みバージョンの状態ファイル
├── docs/                       # ドキュメント
├── scripts/
│   ├── eval_prompt.py          # プロンプト評価スクリプト
│   └── ground_truth.csv       # 評価用の正解データ
├── src/
│   ├── __init__.py
│   ├── main.py                 # エントリポイント
│   ├── github_client.py        # GitHub API クライアント
│   ├── classifier.py           # Gemini による分類・要約
│   ├── notifier.py             # Slack 通知
│   └── state.py                # 状態管理
├── .env.example                # 環境変数テンプレート
├── CLAUDE.md                   # Claude Code 用プロジェクト設定
├── pyproject.toml
└── uv.lock
```

## プロンプト品質管理

Gemini の分類精度を維持・改善するため、正解データベースの評価パイプラインを用意しています。

### 正解データ（Ground Truth）

`scripts/ground_truth.csv` に正解データを格納しています。

```csv
version,category,text
2.1.47,Bugfix,Fixed FileWriteTool line counting to preserve intentional trailing blank lines ...
2.1.47,Improvement,"Improved VS Code plan preview: auto-updates as Claude iterates, ..."
```

| 列 | 説明 |
|----|------|
| `version` | リリースバージョン |
| `category` | 正解カテゴリ（Feature / Improvement / Change / Breaking / Bugfix） |
| `text` | リリースノートの原文 |

#### 正解データの作成

```bash
# 特定バージョンを指定して草案を生成
uv run python scripts/build_truth.py --versions 2.1.45,2.1.49,2.1.47

# 直近 N 件のリリースから草案を生成
uv run python scripts/build_truth.py --count 20
```

先頭動詞（Added → Feature、Fixed → Bugfix 等）で仮分類した草案が `scripts/ground_truth.csv` に出力されます。`Unknown` と分類された項目は手動でカテゴリを割り当ててください。

リリースの選定基準は `docs/ground-truth-selection.md` を参照してください。

### 評価の実行

```bash
uv run python scripts/eval_prompt.py
```

正解データのバージョンに対して Gemini 分類を実行し、項目レベルで突き合わせます。結果は `scripts/eval_result_<timestamp>.csv` に出力されます。

**最重要指標は FN（通知漏れ）= 0 件** — 通知すべき項目が漏れないことがハード目標です。FP（過検出）は許容します。

### Claude Code Skills

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) のカスタムスキルで上記の作業を自動化できます。

| スキル | 説明 |
|--------|------|
| `/build-truth` | 正解データの選定・構築。パターンのバリエーションを網羅する 3〜5 リリースを選定し、`ground_truth.csv` を生成 |
| `/tune-prompt` | 分類プロンプトの自動評価・最適化。正解データに対して `src/prompts.py` の `SYSTEM_PROMPT` を反復的に改善（最大 3 回） |

#### ワークフロー

1. `/build-truth` で評価用の正解データを作成
2. `/tune-prompt` で現在のプロンプトの精度を評価し、FN = 0 を目指して自動改善

