# PLCEmulator 開発タスク

> [!WARNING] **重大な未配線・未接続の課題**
> 現在、TCPは3Eバイナリ電文を解析・実行して応答しますが、**UDPサーバ（`udp_server.py`）は受信処理がpassのまま**です。1E/4E/SLMPなど他形式の実通信接続も未完了です。
> また、`main.py` における Web サーバ（FastAPI）と PLC サーバの統合起動、通信ログの WebSocket 配信も未配線です。

> **ステータス凡例**:
> - `- [x]` **完了**: 実装・接続およびテスト完了
> - `- [ ]` **未完了 / 要対応**: 未着手、または単体実装のみでサーバ未接続・実通信不可
>
> **最終更新**: 2026-10-08 (実通信パイプライン検証結果反映)

---

## 進捗サマリー

| フェーズ | 完了 / 全体 | 進捗率 | 状態と主な未対応事項 |
| :--- | :---: | :---: | :--- |
| **Phase 1: コア基盤** | 9 / 11 | 81.8% | TCPの3Eバイナリ応答は実装済み。**UDPの受信処理はpass**、`main.py`の統合配線未完 |
| **Phase 2: MC 3Eフレーム** | 7 / 7 | 100% | 単体実装とTCP経由の3Eバイナリ読書を確認済み |
| **Phase 3: 1E / 4E / SLMP + ASCII** | 6 / 7 | 85.7% | **3E ASCII未対応**、1E/4E/SLMPの実通信未接続 |
| **Phase 4: スクリプトエンジン** | 6 / 6 | 100% | 単体エンジン・DSL・サンプル完備 |
| **Phase 5: Web UI** | 12 / 13 | 92.3% | 画面・API・i18n完備、**通信ログのサーバ側ブロードキャスト未配線** |
| **Phase 6: 仕上げ** | 2 / 5 | 40.0% | TCPの3E実通信テストは追加済み。**UDPを含む全体統合テスト**、エラー切替、DSLドキュメントが未完 |
| **合計** | **42 / 49** | **85.7%** | **UDPおよび他形式の実通信接続が未完了** |

---

## Phase 1: コア基盤 (9/11 完了)
- [x] プロジェクト構造作成（ディレクトリ、`__init__.py`）
- [x] `requirements.txt` 作成（※pyproject.toml (uv) にて依存関係管理を構成完了）
- [ ] `main.py` エントリーポイント（⚠️ **要対応**: Web UIとPLCサーバの同時起動、プロトコルハンドラーのDI・初期化配線が未実装）
- [x] `src/config.py` 設定管理
- [x] `src/protocol/constants.py` 全定数定義
- [x] `src/device/device_definition.py` デバイス型定義
- [x] `src/device/plc_models.py` PLC機種プロファイル
- [x] `src/device/device_manager.py` デバイスメモリ管理
- [x] `src/server/tcp_server.py` TCPサーバ（3Eバイナリの読書・レイテンシ・応答を実通信で確認。1E/4E/SLMP等は別途対応）
- [ ] `src/server/udp_server.py` UDPサーバ（⚠️ **重大**: `datagram_received`が`pass`のスタブ状態。プロトコル処理・応答送信パイプラインが未接続）
- [x] `src/server/latency.py` レイテンシエミュレータ（単体実装・テスト完了）

## Phase 2: MCプロトコル 3Eフレーム (7/7 完了)
- [x] `src/protocol/base.py` プロトコルハンドラー基底
- [x] `src/protocol/device_parser.py` デバイスアドレス解析
- [x] `src/protocol/mc_frame_3e.py` 3Eフレーム（バイナリ・単体実装完了）
- [x] `src/protocol/command_processor.py` コマンド処理（単体実装完了）
- [x] ユニットテスト: `test_device_manager.py`
- [x] ユニットテスト: `test_mc_frame_3e.py`
- [x] ユニットテスト: `test_command_processor.py`
*(※注: 3EバイナリのTCP読書は実通信テストあり。UDPと他形式の実通信は未対応)*

## Phase 3: 1E / 4E / SLMP + ASCII (6/7 完了)
- [x] `src/protocol/mc_frame_1e.py` 1Eフレーム（単体実装完了）
- [x] `src/protocol/mc_frame_4e.py` 4Eフレーム（単体実装完了）
- [x] `src/protocol/slmp_handler.py` SLMP拡張デバイス指定（単体実装完了）
- [ ] 3Eフレーム ASCIIモード対応（⚠️ **未対応**: バイナリモードのみ実装完了）
- [x] モニタ登録/実行コマンド (`0801`, `0802` 単体実装完了)
- [x] リモートRUN/STOPコマンド (`1001`, `1002` 単体実装完了)
- [x] ユニットテスト追加 (`test_mc_frame_1e.py`, `test_mc_frame_4e.py`, `test_slmp_handler.py`)

## Phase 4: スクリプトエンジン (6/6 完了)
- [x] `src/scripting/builtins.py` 組み込み関数
- [x] `src/scripting/evaluator.py` 安全な式評価器
- [x] `src/scripting/parser.py` YAML DSLパーサー
- [x] `src/scripting/engine.py` スクリプト実行エンジン
- [x] サンプルスクリプト作成 (`scripts/examples/*.yaml` 9種)
- [x] ユニットテスト追加 (`test_builtins.py`, `test_evaluator.py`, `test_script_parser.py`, `test_script_engine.py`)

## Phase 5: Web UI (12/13 完了)
- [x] `src/web/app.py` FastAPI セットアップ
- [x] `src/web/api_routes.py` REST API
- [x] `src/web/websocket_handler.py` WebSocket
- [x] `static/index.html` メインページ
- [x] `static/css/style.css` スタイルシート
- [x] `static/js/app.js` メインアプリ
- [x] `static/js/device_monitor.js` デバイスモニタ
- [ ] `static/js/comm_log.js` 通信ログ（⚠️ **要対応**: JS側の受信処理はあるが、サーバ側で送受信パケットをWebSocketへブロードキャストする処理が未実装）
- [x] `static/js/settings.js` 設定画面
- [x] `static/js/script_editor.js` スクリプトエディタ
- [x] `static/js/i18n.js` 多言語対応
- [x] `src/i18n/ja.json` 日本語翻訳
- [x] `src/i18n/en.json` 英語翻訳

## Phase 6: 仕上げ (2/5 完了)
- [x] デバイス値永続化（JSON保存/読込: `src/persistence/persistence_manager.py`）
- [ ] エラー応答切替機能（⚠️ **未完了**: ConfigManagerにプロパティのみ保持、プロトコル層・UIへの反映が未実装）
- [ ] 全体統合テスト（TCP経由の3Eバイナリ読書・遅延・再接続のテストは追加済み。UDPやWeb UIを含む全体統合テストは未完）
- [x] `README.md` 作成 (`README.md`, `README.ja.md`)
- [ ] `docs/script_dsl_reference.md` DSLリファレンス（⚠️ **未作成**: ファイルが存在しない）
