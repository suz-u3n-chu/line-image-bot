# LINE Bot with Nano Banana Pro Image Generation

AI画像生成機能を持つLINE Botです。GoogleのNano Banana Pro（Gemini 3 Pro Image Preview）を使用して、テキストメッセージから高品質な画像を生成します。

## ✨ 特徴

- 🤖 **LINE Bot統合**: LINEアプリから直接画像生成
- 🎨 **Nano Banana Pro**: Googleの最新AI画像生成モデル使用
  - 最大4K解像度
  - 高度なテキストレンダリング
  - 物理的に正確な照明とフォトリアリスティックな出力
- ☁️ **Cloudinaryホスティング**: 生成画像の安全なクラウドストレージ
- ⚡ **非同期処理**: 即座の応答と画像のプッシュ配信

## 📋 前提条件

以下のアカウントが必要です：

1. **LINE Developers アカウント**
   - [LINE Developers Console](https://developers.line.biz/)でアカウント作成
   
2. **Google AI Studio アカウント**
   - [Google AI Studio](https://aistudio.google.com/)でAPIキー取得
   
3. **Cloudinary アカウント**
   - [Cloudinary](https://cloudinary.com/)で無料アカウント作成

## 🚀 セットアップ

### 1. LINE Bot チャンネルの作成

1. [LINE Developers Console](https://developers.line.biz/)にログイン
2. 新しいプロバイダーを作成（または既存のものを選択）
3. **Messaging API**チャンネルを作成
4. チャンネル設定から以下を取得：
   - **Channel Secret**（Basic settings タブ）
   - **Channel Access Token**（Messaging API タブで発行）

### 2. Google AI Studio API キーの取得

1. [Google AI Studio](https://aistudio.google.com/apikey)にアクセス
2. **Create API Key**をクリック
3. APIキーをコピー（このキーでGemini APIにアクセス可能）

### 3. Cloudinary アカウント設定

1. [Cloudinary](https://cloudinary.com/)で無料アカウント作成
2. ダッシュボードから**CLOUDINARY_URL**をコピー
   - 形式: `cloudinary://api_key:api_secret@cloud_name`

### 4. プロジェクトのセットアップ

```bash
# リポジトリをクローン（または作成）
cd LINEbanana

# 仮想環境の作成（推奨）
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数ファイルの作成
copy .env.example .env  # Windows
# cp .env.example .env  # macOS/Linux
```

### 5. 環境変数の設定

`.env`ファイルを編集して、取得した認証情報を設定：

```env
LINE_CHANNEL_ACCESS_TOKEN=your_actual_line_channel_access_token
LINE_CHANNEL_SECRET=your_actual_line_channel_secret
GOOGLE_API_KEY=your_actual_google_ai_studio_api_key
CLOUDINARY_URL=cloudinary://your_api_key:your_api_secret@your_cloud_name
PORT=5000
```

## 💻 ローカル開発

### サーバーの起動

```bash
# Flask 開発サーバーで起動
python app.py
```

サーバーは `http://localhost:5000` で起動します。

### ngrokでテスト（ローカル環境）

LINEはHTTPSエンドポイントが必要なため、ローカルでテストする場合はngrokを使用：

```bash
# ngrokのインストール（未インストールの場合）
# https://ngrok.com/download

# トンネルの作成
ngrok http 5000
```

ngrokが提供するHTTPS URLをコピーして、LINE Developers ConsoleのWebhook URLに設定：
```
https://your-ngrok-url.ngrok.io/callback
```

## 🌐 デプロイ

### Renderへのデプロイ

1. [Render](https://render.com/)でアカウント作成
2. **New** → **Web Service**を選択
3. GitHubリポジトリを接続
4. 設定：
   - **Name**: 任意の名前
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. 環境変数を追加（Environment タブ）：
   - `LINE_CHANNEL_ACCESS_TOKEN`
   - `LINE_CHANNEL_SECRET`
   - `GOOGLE_API_KEY`
   - `CLOUDINARY_URL`
6. デプロイ後、提供されたURLを使用してLINE Webhook URLを設定：
   ```
   https://your-app-name.onrender.com/callback
   ```

### Google Cloud Runへのデプロイ

1. `Dockerfile`を作成：

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
```

2. Google Cloud CLIでデプロイ：

```bash
gcloud run deploy line-bot \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated
```

3. 環境変数を設定：

```bash
gcloud run services update line-bot \
  --set-env-vars LINE_CHANNEL_ACCESS_TOKEN=your_token,LINE_CHANNEL_SECRET=your_secret,GOOGLE_API_KEY=your_key,CLOUDINARY_URL=your_url
```

### LINE Webhook URLの設定

1. LINE Developers Consoleに戻る
2. Messaging API タブで**Webhook URL**を設定：
   ```
   https://your-deployed-url.com/callback
   ```
3. **Verify**ボタンをクリックして接続を確認
4. **Use webhook**を有効化

## 📱 使い方

1. LINE Developers ConsoleでQRコードをスキャンしてBotを友達追加
2. Botにテキストメッセージを送信
   - 例: "夕焼けの富士山"
   - 例: "サイバーパンクな東京の街並み"
   - 例: "かわいい猫のイラスト"
3. Botが「画像を生成中です...」と応答
4. 数秒後、生成された画像が送信されます！

## 🎨 Nano Banana Pro の特徴

このBotはGoogle最新のNano Banana Pro（Gemini 3 Pro Image Preview）を使用しています：

- **高解像度**: 最大4K画質の画像生成
- **高度な推論**: シーンを計画してからレンダリング
- **優れたテキスト**: 画像内のテキストが明瞭で正確
- **多言語対応**: 複雑なスクリプトと複数言語をサポート
- **フォトリアリスティック**: 物理的に正確な照明と質感

## 🔧 トラブルシューティング

### Webhook検証が失敗する

- `.env`ファイルの`LINE_CHANNEL_SECRET`が正しいか確認
- サーバーがHTTPSで公開されているか確認（ngrokまたはデプロイ済み）

### 画像が生成されない

- `GOOGLE_API_KEY`が有効か確認
- Google AI StudioでGemini APIが有効化されているか確認
- APIクォータ制限に達していないか確認

### 画像が送信されない

- `CLOUDINARY_URL`が正しい形式か確認
- Cloudinaryアカウントが有効か確認

### エラーログの確認

```bash
# ローカル環境
# コンソールに出力されます

# Render
# Dashboard → Logs タブで確認

# Cloud Run
gcloud run logs read line-bot --limit 50
```

## 📄 ライセンス

MIT License

## 🙏 謝辞

- [LINE Messaging API](https://developers.line.biz/ja/docs/messaging-api/)
- [Google Gemini API](https://ai.google.dev/)
- [Nano Banana Pro](https://deepmind.google/technologies/imagen-3/)
- [Cloudinary](https://cloudinary.com/)

---

**注意**: このBotは画像生成APIを使用するため、使用量に応じて料金が発生する可能性があります。各サービスの料金体系を確認してください。
