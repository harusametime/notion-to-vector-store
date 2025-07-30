# Notion to Vector Database Pipeline

Notionからデータを抽出し、Amazon Bedrockを使用してエンベディングを生成し、DataStax Astra DBに保存してベクトル検索とセマンティック類似性を実現する完全なパイプラインです。

## 🚀 機能

- **Notion統合**: Notionワークスペースからすべてのページとコンテンツを抽出
- **AIエンベディング**: Amazon Bedrock Titanモデルを使用して高品質なエンベディングを生成
- **ベクトルデータベース**: セマンティック検索のためにAstra DBにエンベディングとメタデータを保存
- **自動コレクション管理**: ベクトルコレクションを自動的に作成
- **豊富なメタデータ**: ページプロパティ、URL、タイムスタンプ、コンテンツブロックを保存
- **スケーラブル**: ページネーションで大きなNotionワークスペースを処理

## 📋 前提条件

### 必要なサービス
- **Notion統合** APIアクセス付き
- **AWSアカウント** Bedrockアクセス付き
- **DataStax Astra DB** アカウント

### 必要な権限
- "コンテンツの読み取り"権限を持つNotion統合
- TitanエンベディングモデルへのAWS Bedrockアクセス
- ベクトル検索機能を持つAstra DB

## 🛠️ セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境設定

認証情報を含む`.env`ファイルを作成してください（`.env.example`を参考にしてください）：

```bash
# Notion設定
NOTION_SECRET=your_notion_integration_token_here
NOTION_CONNECTION=your_notion_connection_id_here

# AWS Bedrock設定
AWS_ACCESS_KEY=your_aws_access_key_here
AWS_SECRET_KEY=your_aws_secret_key_here
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=amazon.titan-embed-text-v2:0

# DataStax Astra DB設定
ASTRA_DB_ENDPOINT=your_astra_db_endpoint_here
ASTRA_DB_KEYSPACE=your_keyspace_name_here
ASTRA_DB_APPLICATION_TOKEN=your_astra_db_token_here
ASTRA_DB_NAME=your_database_name_here
VECTOR_COLLECTION_NAME=your_collection_name_here
```

### 3. 認証情報の取得

#### Notion統合
1. [Notion Integrations](https://www.notion.so/my-integrations) にアクセス
2. 新しい統合を作成
3. "Internal Integration Token"をコピー
4. ワークスペースのページに統合を追加

#### AWS Bedrock
1. AWSコンソールにアクセスしてBedrockに移動
2. Titanエンベディングモデルへのアクセスをリクエスト
3. Bedrock権限を持つIAM認証情報を作成
4. アクセスキーとシークレットキーをコピー

#### Astra DB
1. 新しいAstra DBデータベースを作成
2. アプリケーショントークンを生成
3. データベースエンドポイントとキースペースを記録
4. ベクトル検索機能を有効化

## 🚀 使用方法

### パイプラインの実行

```bash
python notion_to_vector_db.py
```

パイプラインは以下を実行します：
1. ✅ Notionワークスペースに接続
2. ✅ アクセス可能なすべてのページを抽出
3. ✅ Amazon Bedrockを使用してエンベディングを生成
4. ✅ Astra DBにベクトルコレクションを作成（必要に応じて）
5. ✅ エンベディングとメタデータでページを保存
6. ✅ 進行状況の更新とサマリーを提供

### 🔄 重複処理の防止とコスト最適化

パイプラインは**重複を自動的に防止**し、**Bedrock APIコストを最小化**します：

- **初回実行**: すべてのページが新規挿入されます
- **再実行時**: 
  - **変更されたページ** → **更新**（最新のコンテンツとベクトルで上書き）
  - **新規ページ** → **新規挿入**
  - **変更なしのページ** → **スキップ**（Bedrock API呼び出しを節約）

**コスト最適化機能:**
- ✅ **タイムスタンプ比較**: Notionの`last_edited_time`を使用
- ✅ **変更検出**: 変更されたページのみ更新
- ✅ **API呼び出し削減**: 未変更ページはスキップ
- ✅ **詳細統計**: 挿入、更新、スキップ数を表示

これにより、同じページの重複エントリが作成されることはなく、Bedrock APIコストも大幅に削減されます。

### 出力例

```
🚀 Notion to Vector Database Pipeline
==================================================
✅ Bedrock client created successfully
✅ Astra DB client created successfully
✅ Vector collection 'vector_collection' created successfully
🔍 Searching for Notion pages...
📄 Found 8 page(s)

📄 Processing page 1/8: 12015dc6-b965-80f2-af2b-ee7fc8a1653b
   🔍 Generating embedding for content...
   💾 Storing in vector database...
   ✅ Successfully stored page 1/8

🎉 Processing completed!
📊 Summary:
   - Total pages found: 8
   - New pages inserted: 1
   - Existing pages updated: 2
   - Pages unchanged (skipped): 5
   - Pages skipped (no content): 0
   - Failed: 0
```

## 📊 データベーススキーマ

### ベクトル化されるデータ

パイプラインは以下のNotionブロックのテキストコンテンツをベクトル化します：

**ベクトル化対象:**
- **段落** (`paragraph`) - 通常のテキストコンテンツ
- **見出し** (`heading_1`, `heading_2`, `heading_3`) - ページタイトルとセクションヘッダー
- **リスト項目** (`bulleted_list_item`, `numbered_list_item`) - リストコンテンツ
- **To-do項目** (`to_do`) - タスクとチェックリストコンテンツ
- **コードブロック** (`code`) - コードスニペットと技術コンテンツ
- **引用** (`quote`) - 引用テキストコンテンツ
- **コールアウト** (`callout`) - ハイライトされた重要なコンテンツ

**ベクトル化されないデータ（メタデータとして保存）:**
- ページプロパティ（タイトル、タグ、日付など）
- ページメタデータ（URL、タイムスタンプ、アーカイブ状態）
- ブロック構造（ブロックID、タイプ）
- 画像、ファイル、動画（URLとして保存）
- リッチテキストフォーマット（プレーンテキストのみ使用）

### データベース構造

パイプラインは以下の構造を持つベクトルコレクションを作成します：

```json
{
  "page_id": "unique_notion_page_id",
  "page_title": "ページタイトル",
  "page_url": "https://notion.so/...",
  "created_time": "2024-01-01T00:00:00Z",
  "last_edited_time": "2024-01-01T00:00:00Z",
  "archived": false,
  "properties": {
    "title": "ページタイトル",
    "tags": ["tag1", "tag2"]
  },
  "content_text": "エンベディング用の完全なテキストコンテンツ",
  "content_blocks": [
    {
      "id": "block_id",
      "type": "paragraph",
      "content": "ブロックコンテンツ"
    }
  ],
  "embedding_model": "amazon.titan-embed-text-v2:0",
  "created_at": "2024-01-01T00:00:00Z",
  "$vector": [0.1, 0.2, ...] // 1024次元のエンベディング
}
```

## 🔍 ベクトル検索

パイプラインを実行した後、Astra DBのベクトル機能を使用してセマンティック検索を実行できます：

```python
from astrapy.db import AstraDB

# データベースに接続
db = AstraDB(
    token="your_token",
    api_endpoint="your_endpoint",
    namespace="your_keyspace"
)

# 類似コンテンツを検索
results = db.collection("your_collection").find(
    {},
    sort={"$vector": your_query_embedding},
    limit=5
)
```

## 🛡️ エラーハンドリング

パイプラインには以下の堅牢なエラーハンドリングが含まれています：
- ✅ 環境変数の不足
- ✅ 無効な認証情報
- ✅ ネットワーク接続の問題
- ✅ コレクション作成の失敗
- ✅ エンベディング生成エラー
- ✅ データベース挿入の失敗

## 📈 パフォーマンス

- **エンベディング生成**: ページあたり約1-2秒
- **データベース保存**: ページあたり約0.5秒
- **メモリ使用量**: 最小限、ページを順次処理
- **ネットワーク**: Astra DBのREST APIに最適化

## 🔧 設定オプション

### 環境変数

| 変数 | 説明 | デフォルト |
|------|------|------------|
| `BEDROCK_MODEL_ID` | エンベディング用のAmazon Bedrockモデル | `amazon.titan-embed-text-v2:0` |
| `AWS_REGION` | Bedrock用のAWSリージョン | `us-east-1` |
| `VECTOR_COLLECTION_NAME` | Astra DBコレクション名 | `vector_collection` |

### エンベディングモデル

パイプラインはAmazon Titanのテキストエンベディングモデルを使用します：
- **次元数**: 1024
- **メトリック**: コサイン類似性
- **品質**: 高品質なセマンティックエンベディング

## 🤝 貢献

1. リポジトリをフォーク
2. 機能ブランチを作成
3. 変更を加える
4. 独自のNotionワークスペースでテスト
5. プルリクエストを送信

## 📄 ライセンス

このプロジェクトはMITライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 🆘 トラブルシューティング

### よくある問題

**"Collection does not exist"**
- パイプラインはコレクションを自動的に作成します
- Astra DBの権限を確認してください
- `.env`のコレクション名を確認してください

**"AWS credentials not found"**
- `.env`ファイルに`AWS_ACCESS_KEY`と`AWS_SECRET_KEY`があることを確認
- AWS認証情報にBedrockアクセスがあることを確認

**"No pages found"**
- Notion統合の権限を確認
- 統合がワークスペースのページに追加されていることを確認
- `NOTION_SECRET`が正しいことを確認

**"Bedrock access denied"**
- AWS BedrockでTitanエンベディングモデルへのアクセスをリクエスト
- Bedrock用のIAM権限を確認

## 📞 サポート

問題や質問がある場合：
1. 上記のトラブルシューティングセクションを確認
2. 認証情報と権限を確認
3. Astra DBとAWS Bedrockのドキュメントを確認
4. GitHubでイシューを開く 