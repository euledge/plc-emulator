# PLCEmulator

[![CI](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml/badge.svg)](https://github.com/euledge/plc-emulator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](pyproject.toml)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

MCプロトコル / SLMP対応のPLC通信エミュレータ

[**English version**](README.md) | [**リリースノート (v0.1.0)**](RELEASE_NOTES_v0.1.0.ja.md)

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
- **全テスト 115件** (単体・統合 99 + E2E 16)

## クイックスタート

```bash
# 依存関係のインストール
uv sync

# 単体・統合テスト実行
uv run pytest

# PLCエミュレータ & Web UI 起動 (共有メモリ・同時起動エントリポイント)
# デフォルトで Web UI: http://127.0.0.1:8000, PLCサーバ: ポート 5000 にバインド
uv run python main.py

# E2Eテスト (初回のみブラウザインストールが必要)
uv run playwright install chromium
uv run pytest tests/test_e2e.py
# ※ ブラウザを表示して動作確認する場合は --headed を付与
# uv run pytest tests/test_e2e.py --headed
```

## プロジェクト構成

```
src/
  config.py              # 設定管理
  device/
    device_manager.py    # デバイスメモリ管理
    plc_models.py        # PLC機種定義
  protocol/
    constants.py         # 定数定義 (フレーム・コマンドID等)
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

`scripts/examples/` に実用的なシミュレーションサンプルを用意しています。Web UI の「Scripts」画面からも直接実行可能です。

| サンプルファイル | 制御種別 | 主な内容 |
|---|---|---|
| `heartbeat.yaml` | `periodic` | 通信生存確認（1秒ごとの M0 点滅・D0 カウンタ更新） |
| `sawtooth.yaml` | `periodic` | D100 へのノコギリ波書き込み |
| `sensor_simulation.yaml` | `periodic` | 温度・圧力・流量の計器信号模擬（正弦波・三角波・ノイズ） |
| `ramp_loop.yaml` | `ramp` | D200 を 0→1000 へ10秒かけて連続変化（ループ） |
| `conditional.yaml` | `conditional` | D100 の閾値に応じた M0 の ON/OFF 切り替え |
| `alarm_interlock.yaml` | `conditional` | 高温警報（ヒステリシス付き）および非常停止インターロック |
| `cylinder_sequence.yaml` | `sequence` | クランプ → 加工 → 排出 → 原点復帰のステップ運転 |
| `tank_level_control.yaml` | 複合 (`periodic` + `conditional`) | タンク水位の物理挙動模擬とポンプ・排水弁の自動制御 |
| `traffic_light.yaml` | `sequence` | 交通信号機の点灯サイクル（青 → 黄 → 赤） |

### 記述例

```yaml
# 1. 定期実行: 温度センサの模擬（正弦波 + ランダムノイズ）
- type: periodic
  interval_ms: 500
  actions:
    - target: D100
      expr: "int(clamp(50 + 25 * sin(t * 0.2) + randint(-1, 1), 0, 100))"

# 2. ランプ加減速: D200 を 0→1000 まで10秒で変化
- type: ramp
  target: D200
  start_value: 0
  end_value: 1000
  duration_ms: 10000
  loop: true

# 3. 条件分岐: 高温警報（75℃以上で警報ON、65℃未満で復帰）
- type: conditional
  interval_ms: 200
  conditions:
    - when: "D100 >= 75"
      actions:
        - target: M100
          value: 1
    - when: "D100 < 65"
      actions:
        - target: M100
          value: 0

# 4. シーケンス: クランプ → 加工 → 排出のステップ工程
- type: sequence
  loop: true
  steps:
    - wait_ms: 1000
      actions:
        - target: D10  # 工程番号
          value: 1
        - target: Y10  # クランプ
          value: 1
    - wait_ms: 2000
      actions:
        - target: D10
          value: 2
        - target: Y11  # 加工
          value: 1
    - wait_ms: 1000
      actions:
        - target: D10
          value: 3
        - target: Y10
          value: 0
        - target: Y11
          value: 0
```

## ライセンス

MIT
