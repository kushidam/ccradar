# Next Actions & 動作確認ガイド

---

## 1. ローカルでの動作確認（最優先）

外部サービスの設定前に、まずローカルで `--dry-run` を使って動作確認する。

### 1.1 Python 環境の準備

```bash
cd /Users/kushidam/develop/work/ccradar

# venv 作成（推奨）
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### 1.2 Gemini API キーの取得

1. https://aistudio.google.com/ にアクセス
2. 「Get API key」→「Create API key」
3. キーをコピー

### 1.3 dry-run で実行

```bash
export GEMINI_API_KEY="取得したキーをここに"

python -m src.main --dry-run
```

**期待される結果:**
- GitHub API から claude-code のリリースを取得
- Gemini で分類・要約
- 標準出力に Feature / Improvement が表示される
- Slack には送信されない
- `data/state.json` も更新されない

**エラーが出た場合のチェックポイント:**

| エラー | 原因 | 対処 |
|--------|------|------|
| `ModuleNotFoundError` | venv 未活性 or パッケージ未インストール | `source .venv/bin/activate && pip install -r requirements.txt` |
| `GEMINI_API_KEY ... is not set` | 環境変数が未設定 | `export GEMINI_API_KEY="..."` を確認 |
| `requests.exceptions.HTTPError: 403` | GitHub API レート制限 | `export GITHUB_TOKEN="ghp_..."` を設定 |
| Gemini API エラー | APIキー無効 or モデル名不正 | Google AI Studio でキーを再確認 |

---

## 2. Slack 通知の確認

### 2.1 Slack Incoming Webhook の作成

1. https://api.slack.com/apps にアクセス
2. 「Create New App」→「From scratch」
3. アプリ名: `Release Radar`（任意）、ワークスペースを選択
4. 左メニュー「Incoming Webhooks」→ ON に切り替え
5. 「Add New Webhook to Workspace」→ 通知先チャンネルを選択
6. Webhook URL をコピー（`https://hooks.slack.com/services/T.../B.../...` 形式）

### 2.2 Slack 通知のテスト

```bash
export GEMINI_API_KEY="取得したキーをここに"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

python -m src.main
```

**期待される結果:**
- Slack チャンネルに通知が届く
- `data/state.json` が更新される（処理済みバージョンが記録される）

### 2.3 2回目の実行で差分検知を確認

```bash
python -m src.main --dry-run
```

**期待される結果:**
- `No new releases found` のログが出て終了（= 差分検知が正しく動作している）

---

## 3. GitHub Actions の設定

### 3.1 コードを push

```bash
git add -A
git commit -m "Initial implementation of Release Radar"
git push origin main
```

### 3.2 GitHub Secrets の登録

リポジトリページ → Settings → Secrets and variables → Actions → 「New repository secret」

| Secret 名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio で取得した API キー |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook の URL |

### 3.3 手動実行でテスト

1. リポジトリの **Actions** タブを開く
2. 左メニュー「**Claude Code Release Radar**」を選択
3. 「**Run workflow**」→ ブランチ `main` を確認 →「**Run workflow**」
4. ジョブの実行ログを確認
5. Slack に通知が届くことを確認
6. `data/state.json` が自動コミットされていることを確認

---

## 4. 確認チェックリスト

- [ ] ローカル dry-run が成功する
- [ ] Gemini API で分類・要約が返ってくる
- [ ] Slack に通知メッセージが届く
- [ ] `data/state.json` にバージョンが記録される
- [ ] 2回目実行で「No new releases」になる（差分検知OK）
- [ ] GitHub にコードを push 済み
- [ ] GitHub Secrets に `GEMINI_API_KEY` と `SLACK_WEBHOOK_URL` を登録済み
- [ ] GitHub Actions 手動実行が成功する
- [ ] 翌日 9:00 JST に自動実行されることを確認

---

## 5. トラブルシューティング

### GitHub Actions が失敗する場合

```
Actions タブ → 失敗したジョブをクリック → ログを確認
```

よくある原因:
- Secrets の名前が間違っている（大文字小文字に注意）
- `permissions: contents: write` がリポジトリ設定で許可されていない
  → Settings → Actions → General → Workflow permissions → 「Read and write permissions」に変更

### state.json の自動コミットが失敗する場合

- リポジトリの Actions 権限で write が許可されているか確認
- ブランチ保護ルールが邪魔していないか確認

### state.json をリセットしたい場合

```bash
# 初期状態に戻す（次回実行時に最新リリースのみ処理）
echo '{}' > data/state.json
git add data/state.json
git commit -m "Reset state"
git push
```
