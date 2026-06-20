# PLCEmulator 開発タスク

## Phase 1: コア基盤
- [ ] プロジェクト構造作成（ディレクトリ、`__init__.py`）
- [ ] `requirements.txt` 作成
- [ ] `main.py` エントリーポイント
- [ ] `src/config.py` 設定管理
- [ ] `src/protocol/constants.py` 全定数定義
- [ ] `src/device/device_definition.py` デバイス型定義
- [ ] `src/device/plc_models.py` PLC機種プロファイル
- [ ] `src/device/device_manager.py` デバイスメモリ管理
- [ ] `src/server/tcp_server.py` TCPサーバ
- [ ] `src/server/udp_server.py` UDPサーバ
- [ ] `src/server/latency.py` レイテンシエミュレータ

## Phase 2: MCプロトコル 3Eフレーム
- [ ] `src/protocol/base.py` プロトコルハンドラー基底
- [ ] `src/protocol/device_parser.py` デバイスアドレス解析
- [ ] `src/protocol/mc_frame_3e.py` 3Eフレーム（バイナリ）
- [ ] `src/protocol/command_processor.py` コマンド処理
- [ ] ユニットテスト: `test_device_manager.py`
- [ ] ユニットテスト: `test_mc_frame_3e.py`
- [ ] ユニットテスト: `test_command_processor.py`

## Phase 3: 1E / 4E / SLMP + ASCII
- [ ] `src/protocol/mc_frame_1e.py` 1Eフレーム
- [ ] `src/protocol/mc_frame_4e.py` 4Eフレーム
- [ ] `src/protocol/slmp_handler.py` SLMP拡張デバイス指定
- [ ] 3Eフレーム ASCIIモード対応
- [ ] モニタ登録/実行コマンド
- [ ] リモートRUN/STOPコマンド
- [ ] ユニットテスト追加

## Phase 4: スクリプトエンジン
- [ ] `src/scripting/builtins.py` 組み込み関数
- [ ] `src/scripting/evaluator.py` 安全な式評価器
- [ ] `src/scripting/parser.py` YAML DSLパーサー
- [ ] `src/scripting/engine.py` スクリプト実行エンジン
- [ ] サンプルスクリプト作成
- [ ] ユニットテスト追加

## Phase 5: Web UI
- [ ] `src/web/app.py` FastAPI セットアップ
- [ ] `src/web/api_routes.py` REST API
- [ ] `src/web/websocket_handler.py` WebSocket
- [ ] `static/index.html` メインページ
- [ ] `static/css/style.css` スタイルシート
- [ ] `static/js/app.js` メインアプリ
- [ ] `static/js/device_monitor.js` デバイスモニタ
- [ ] `static/js/comm_log.js` 通信ログ
- [ ] `static/js/settings.js` 設定画面
- [ ] `static/js/script_editor.js` スクリプトエディタ
- [ ] `static/js/i18n.js` 多言語対応
- [ ] `src/i18n/ja.json` 日本語翻訳
- [ ] `src/i18n/en.json` 英語翻訳

## Phase 6: 仕上げ
- [ ] デバイス値永続化（JSON保存/読込）
- [ ] エラー応答切替機能
- [ ] 全体統合テスト
- [ ] `README.md` 作成
- [ ] `docs/script_dsl_reference.md` DSLリファレンス
