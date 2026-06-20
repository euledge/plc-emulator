# PLCEmulator

[![CI](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml/badge.svg)](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)

MCプロトコル / SLMP対応のPLC通信エミュレータ

[**English version**](README.md)

> **GitHub トピック候補**: `plc`, `mc-protocol`, `slmp`, `mitsubishi`, `emulator`, `fastapi`, `plc-simulator`, `python`, `scada`, `industrial-automation`

## 機能

- **MC プロトコル** 3E/1E/4E フレーム + **SLMP** 対応
- **TCP / UDP** サーバ
- **デバイスメモリ** 読み書き (ビット・ワード・バッチ)
- **PLC機種** 定義 (Q/L/FX) + 範囲チェック
- **遅延エミュレーション** (なし/固定/ランダム/正規分布/タイムアウト)
- **スクリプティング** (YAML DSL + AST安全評価)
  - 定期書込 / ランプ / 条件分岐 / シーケンス
- **Web UI** (FastAPI + ダークテーマ)
  - 設定パネル / デバイスモニタ / 通信ログ / スクリプトエディタ
  - WebSocket リアルタイム更新 / i18n (日本語・英語)
- **状態保存** JSON ファイルへの save/load
- **全テスト 113件** (ユニット90 + Web API 7 + 永続化 5 + E2E 16)

## クイックスタート

```bash
# インストール
uv sync

# 全テスト実行
uv run pytest

# サーバ起動 (http://localhost:8000)
uv run uvicorn src.web.app:create_app --factory --reload

# E2Eテスト (別ターミナルでサーバ停止中に)
uv run pytest tests/test_e2e.py --headed
```

## プロジェクト構成

```
src/
  config.py              # 設定管理
  constants.py           # 定数定義
  device/
    device_manager.py    # デバイスメモリ管理
    plc_models.py        # PLC機種定義
  protocol/
    base.py              # プロトコル基底クラス
    device_parser.py     # デバイス番号解析
    mc_frame_3e.py       # MC 3Eフレーム
    mc_frame_1e.py       # MC 1Eフレーム
    mc_frame_4e.py       # MC 4Eフレーム
    slmp_handler.py      # SLMP
    command_processor.py # コマンド処理
  server/
    tcp_server.py        # TCPサーバ
    udp_server.py        # UDPサーバ
    latency.py           # 遅延エミュレータ
  scripting/
    builtins.py          # 組み込み関数
    evaluator.py         # AST評価器
    parser.py            # YAMLパーサ
    engine.py            # スクリプト実行エンジン
  web/
    app.py               # FastAPIアプリ
    api_routes.py        # APIルート
    websocket_handler.py # WebSocket管理
  i18n/
    i18n.py              # 翻訳ローダ
    ja.json / en.json    # 翻訳データ
  persistence/
    persistence_manager.py # JSON保存/読込
static/
  index.html             # Web UI
  css/style.css
  js/                    # フロントエンドJS
scripts/examples/        # サンプルスクリプト
tests/                   # テスト
```

## OpenAPI

OpenAPI 3.1 仕様書: [`docs/openapi.json`](docs/openapi.json)
(14 エンドポイント, 7 スキーマ)

## API一覧

| Method | Path | 説明 |
|--------|------|------|
| GET | `/api/config` | 設定取得 |
| PUT | `/api/config` | 設定更新 |
| GET | `/api/devices/{type}` | デバイス一括読込 |
| PUT | `/api/devices/{type}/{addr}` | デバイス書込 |
| GET | `/api/latency/stats` | 遅延統計 |
| PUT | `/api/latency/config` | 遅延設定 |
| GET | `/api/scripts` | スクリプト一覧 |
| GET | `/api/scripts/{name}` | スクリプト内容 |
| PUT | `/api/scripts/{name}` | スクリプト保存 |
| POST | `/api/scripts/{name}/start` | スクリプト開始 |
| POST | `/api/scripts/{name}/stop` | スクリプト停止 |
| POST | `/api/save` | 状態保存 |
| POST | `/api/load` | 状態読込 |
| GET | `/api/i18n/{lang}` | 翻訳データ |
| WS | `/ws` | WebSocket |

## スクリプト例

```yaml
# 定期実行 (D100 に sawtooth 値を書き込み)
- type: periodic
  interval_ms: 1000
  actions:
    - target: D100
      expr: "t % 1000"

# ランプ (D200 を 0→1000 まで10秒で、ループ)
- type: ramp
  target: D200
  start_value: 0
  end_value: 1000
  duration_ms: 10000
  loop: true

# 条件分岐 (D100 > 500 で M0 ON)
- type: conditional
  interval_ms: 200
  conditions:
    - when: "D100 > 500"
      actions:
        - target: M0
          value: 1
    - when: "D100 <= 500"
      actions:
        - target: M0
          value: 0
```

## ライセンス

MIT
