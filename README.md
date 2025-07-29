# Notion Database ID Finder

このスクリプトは、Notion APIを使用してデータベースIDを取得するためのツールです。

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env` ファイルを作成し、Notionのインテグレーショントークンを設定してください：

```bash
NOTION_SECRET=your_notion_integration_token_here
```

### 3. Notionインテグレーションの設定

1. [Notion Integrations](https://www.notion.so/my-integrations) にアクセス
2. 新しいインテグレーションを作成
3. インテグレーショントークンをコピーして `.env` ファイルに設定
4. データベースにインテグレーションを追加（データベースの設定 → コネクション → インテグレーションを追加）

## 使用方法

### すべてのデータベースを表示

```bash
python get_notion_databases.py
```

### 特定のデータベースの詳細を表示

```bash
python get_notion_databases.py --database <database_id>
```

## 出力例

```
🔍 Notion Database ID Finder
========================================
📊 Found 2 database(s):
--------------------------------------------------------------------------------
1. Database ID: 12345678-1234-1234-1234-123456789abc
   Title: My Project Database
   URL: https://notion.so/12345678123412341234123456789abc

2. Database ID: 87654321-4321-4321-4321-cba987654321
   Title: Task Tracker
   URL: https://notion.so/87654321432143214321cba987654321

💡 To get detailed information about a specific database, run:
python get_notion_databases.py --database <database_id>
```

## 注意事項

- Notionインテグレーションがデータベースにアクセス権限を持っていることを確認してください
- データベースIDは、NotionのURLからも取得できます（URLの最後の部分）
- インテグレーショントークンは機密情報なので、`.env` ファイルをGitにコミットしないでください 