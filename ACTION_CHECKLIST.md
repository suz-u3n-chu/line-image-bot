# あなたがやること - 完全ガイド

以下の手順に従ってください。私が準備できることは全て完了しています。

---

## ✅ 準備完了（私がやりました）
- ✅ Gitリポジトリ初期化
- ✅ コードをコミット
- ✅ ブランチをmainに変更

---

## 🎯 あなたがやること（3ステップのみ）

### 【ステップ1】GitHubリポジトリ作成（5分）

#### 1-1. GitHubにアクセス
ブラウザで開く: **https://github.com/new**

#### 1-2. リポジトリ設定
以下のように入力：

| 項目 | 入力内容 |
|------|----------|
| **Repository name** | `line-image-bot` |
| **Description** | `LINE Bot with Google Imagen 3` （任意） |
| **Public/Private** | どちらでもOK（Privateを推奨） |
| **Add a README file** | ✅ **チェックを外す** |
| **Add .gitignore** | 選択しない |
| **Choose a license** | 選択しない |

#### 1-3. 作成
「**Create repository**」ボタンをクリック

#### 1-4. URLをコピー
作成後、画面に表示される以下のようなURLをコピー：
```
https://github.com/あなたのユーザー名/line-image-bot.git
```

#### 1-5. PowerShellで以下を実行

**コピーしたURLを使って以下を実行してください**：

```powershell
cd C:\Users\skait\LINEbanana

# ここに↓あなたのGitHubリポジトリURLを貼り付け
git remote add origin https://github.com/あなたのユーザー名/line-image-bot.git

# プッシュ
git push -u origin main
```

GitHubのユーザー名とパスワードを聞かれたら入力してください。

✅ 完了したら次へ

---

### 【ステップ2】Renderデプロイ設定（10分）

#### 2-1. Renderにアクセス
ブラウザで開く: **https://render.com**

#### 2-2. サインアップ
「**Get Started**」または「**Sign Up**」をクリック
→ 「**Sign up with GitHub**」を選択
→ GitHubアカウントで認証

#### 2-3. Web Service作成
1. Renderダッシュボードで「**New +**」ボタンをクリック
2. 「**Web Service**」を選択

#### 2-4. リポジトリ接続
1. 「**Connect a repository**」画面で `line-image-bot` を探す
2. 右側の「**Connect**」ボタンをクリック

#### 2-5. 設定を入力

以下を**正確に**入力してください：

```
Name: line-image-bot
Region: Singapore (またはOregon)
Branch: main
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Instance Type: Free （無料プランを選択）
```

#### 2-6. 環境変数を追加

画面を下にスクロールして「**Environment Variables**」セクションを見つける

「**Add Environment Variable**」を4回クリックして、以下を追加：

**1つ目**:
```
Key: LINE_CHANNEL_ACCESS_TOKEN
Value: （.envファイルから LINE_CHANNEL_ACCESS_TOKEN の値をコピペ）
```

**2つ目**:
```
Key: LINE_CHANNEL_SECRET
Value: （.envファイルから LINE_CHANNEL_SECRET の値をコピペ）
```

**3つ目**:
```
Key: GOOGLE_API_KEY
Value: （.envファイルから GOOGLE_API_KEY の値をコピペ）
```

**4つ目**:
```
Key: CLOUDINARY_URL
Value: （.envファイルから CLOUDINARY_URL の値をコピペ）
```

#### 2-7. デプロイ開始
一番下の「**Create Web Service**」ボタンをクリック

⏳ デプロイに5-10分かかります。完了すると画面上部に URL が表示されます：
```
https://line-image-bot-xxxx.onrender.com
```

**このURLをコピーしてください！**

✅ 完了したら次へ

---

### 【ステップ3】LINE Webhook設定（3分）

#### 3-1. LINE Developers Consoleにアクセス
ブラウザで開く: **https://developers.line.biz/console/**

#### 3-2. チャンネルを開く
作成したMessaging APIチャンネルをクリック

#### 3-3. Messaging APIタブ
「**Messaging API**」タブをクリック

#### 3-4. Webhook URL設定
下にスクロールして「**Webhook settings**」セクションを探す

「**Webhook URL**」の「Edit」ボタンをクリック

以下を入力（RenderのURLの最後に `/callback` を追加）：
```
https://line-image-bot-xxxx.onrender.com/callback
```

「**Update**」をクリック

#### 3-5. 接続確認
「**Verify**」ボタンをクリック
→ 「Success」と表示されればOK！

#### 3-6. Webhookを有効化
「**Use webhook**」のスイッチを **ON** にする

✅ 完了！

---

## 🎉 動作確認

1. LINE Developers Consoleの「**Messaging API**」タブ
2. QRコードをスマホでスキャンして友だち追加
3. トークで以下を送信：
   ```
   夕焼けの富士山
   ```
4. 「🎨 画像を生成中です...」と返信が来る
5. 数秒後、画像が送られてくる

**成功です！！** 🎊

---

## 🆘 困ったら

各ステップで問題があれば、どこで詰まったか教えてください。すぐにサポートします！

---

**まずは【ステップ1】GitHubリポジトリ作成から始めてください！**
