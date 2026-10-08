# PLCEmulator 開発タスク

## Phase 1: コア基盤
- [x] プロジェクト構造作成（ディレクトリ、`__init__.py`）
- [x] `requirements.txt` 作成（`pyproject.toml` / `uv.lock` を採用）
- [x] `main.py` エントリーポイント
- [x] `src/config.py` 設定管理
- [x] `src/protocol/constants.py` 全定数定義
- [x] `src/device/device_definition.py` デバイス型定義
- [x] `src/device/plc_models.py` PLC機種プロファイル
- [x] `src/device/device_manager.py` デバイスメモリ管理
- [x] `src/server/tcp_server.py` TCPサーバ（3Eバイナリ送受信・再接続・遅延適用に対応）
- [ ] `src/server/udp_server.py` UDPサーバ（ソケット起動のみ実装、電文送受信未対応）
- [x] `src/server/latency.py` レイテンシエミュレータ

## Phase 2: MCプロトコル 3Eフレーム
- [x] `src/protocol/base.py` プロトコルハンドラー基底
- [x] `src/protocol/device_parser.py` デバイスアドレス解析
- [x] `src/protocol/mc_frame_3e.py` 3Eフレーム（バイナリ）
- [x] `src/protocol/command_processor.py` コマンド処理
- [x] ユニットテスト: `test_device_manager.py`
- [x] ユニットテスト: `test_mc_frame_3e.py`
- [x] ユニットテスト: `test_command_processor.py`

## Phase 3: 1E / 4E / SLMP + ASCII
- [x] `src/protocol/mc_frame_1e.py` 1Eフレーム（ハンドラー実装済み、サーバ未統合）
- [x] `src/protocol/mc_frame_4e.py` 4Eフレーム（ハンドラー実装済み、サーバ未統合）
- [x] `src/protocol/slmp_handler.py` SLMP拡張デバイス指定
- [ ] 3Eフレーム ASCIIモード対応
- [x] モニタ登録/実行コマンド
- [x] リモートRUN/STOPコマンド
- [x] ユニットテスト追加

## Phase 4: スクリプトエンジン
- [x] `src/scripting/builtins.py` 組み込み関数
- [x] `src/scripting/evaluator.py` 安全な式評価器
- [x] `src/scripting/parser.py` YAML DSLパーサー
- [x] `src/scripting/engine.py` スクリプト実行エンジン
- [x] サンプルスクリプト作成
- [x] ユニットテスト追加

## Phase 5: Web UI
- [x] `src/web/app.py` FastAPI セットアップ
- [x] `src/web/api_routes.py` REST API
- [x] `src/web/websocket_handler.py` WebSocket
- [x] `static/index.html` メインページ
- [x] `static/css/style.css` スタイルシート
- [x] `static/js/app.js` メインアプリ
- [x] `static/js/device_monitor.js` デバイスモニタ
- [x] `static/js/comm_log.js` 通信ログ
- [x] `static/js/settings.js` 設定画面
- [x] `static/js/script_editor.js` スクリプトエディタ
- [x] `static/js/i18n.js` 多言語対応
- [x] `src/i18n/ja.json` 日本語翻訳
- [x] `src/i18n/en.json` 英語翻訳

## Phase 6: 仕上げ
- [x] デバイス値永続化（JSON保存/読込）
- [ ] エラー応答切替機能
- [ ] 全体統合テスト（TCP 3E読書・再接続・遅延およびWeb E2Eは検証済み。UDPやASCIIの統合は未完）
- [x] `README.md` 作成
- [ ] `docs/script_dsl_reference.md` DSLリファレンス
