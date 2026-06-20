# ADR-001: 技術スタック選定

## ステータス
**承認済み** (2026-06-20)

## コンテキスト
PLC通信エミュレータを開発するにあたり、技術スタックを決定する必要がある。  
参考ツール（plc-memo.com DummyPLC）は C# / .NET + WPF で開発されているが、ユーザーには以下の制約がある:

- Windowsの開発環境（Visual Studio等）を持っていない
- Windows以外のOS（macOS, Linux）でも実行できるようにしたい

## 検討した選択肢

### 選択肢1: C# / .NET 8.0 + Avalonia UI
- **メリット**: 参考ツールと同じ言語、強い型付け、Avaloniaでクロスプラットフォーム
- **デメリット**: .NET SDKのインストールが必要、Avaloniaはメインストリームではない

### 選択肢2: Python + Web UI（FastAPI + HTML/CSS/JS）
- **メリット**: クロスプラットフォーム、特別な開発環境不要、Pythonは広く普及、ブラウザUIはOS依存なし、structモジュールでバイナリ処理可能
- **デメリット**: GILによる並行処理制限（asyncioで緩和可能）、実行速度はC#より遅い

### 選択肢3: Electron（Node.js + HTML/CSS/JS）
- **メリット**: リッチなデスクトップUI、クロスプラットフォーム
- **デメリット**: メモリ消費大、Node.jsでのバイナリプロトコル処理がやや面倒

## 決定
**選択肢2: Python + Web UI** を採用する。

## 理由
1. **クロスプラットフォーム**: Python + ブラウザの組み合わせはOS依存がなく、どの環境でも動作する
2. **セットアップの容易さ**: `pip install` + `python main.py` で起動可能。特別なIDEやSDKは不要
3. **バイナリ処理**: `struct` モジュールでPLCプロトコルのバイナリ解析が直感的に書ける
4. **非同期処理**: `asyncio` によるTCP/UDPサーバの非同期処理が標準ライブラリで実現可能
5. **Web UI**: ブラウザベースのUIはOS依存がなく、リアルタイム更新もWebSocketで実現可能
6. **パフォーマンス**: 50msのレスポンス要件はPythonでも十分達成可能（dict + arrayのO(1)アクセス、structによるバイト操作）

## 構成
| 要素 | 技術 |
|:--|:--|
| 言語 | Python 3.10+ |
| PLCサーバ | asyncio |
| Web API | FastAPI |
| Web UI | HTML / CSS / JavaScript |
| スクリプトDSL | YAML + ast.parseベース式評価 |
| データ永続化 | JSON |
| テスト | pytest |
