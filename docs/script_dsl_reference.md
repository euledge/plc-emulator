# スクリプトDSL 利用リファレンス (Script DSL Reference)

PLCEmulatorに組み込まれているYAMLベースのデバイスメモリスクリプトDSLの仕様・構文・利用方法のリファレンスです。

---

## 1. 概要 (Overview)

PLCEmulatorのスクリプトエンジンは、PLC本体側のラダープログラムや実機設備を模倣し、センサー値の変化、アラーム連動、シーケンス制御、波形生成などの動作をバックグラウンドで自律実行するための機能です。

### 主な特徴
- **安全なサンドボックス評価**: Pythonの`ast`モジュールによる構文解析を行い、危険な関数（`eval`, `exec`, `import`, ファイル操作, ネットワーク通信等）を一切排除した安全な式評価を実行します。
- **4つのスクリプトタイプ**: `periodic` (周期実行), `conditional` (条件分岐), `sequence` (順序制御), `ramp` (ランプ変化) に対応。
- **リアルタイム連動**: 式中でデバイスメモリ（`D100`, `M0` 等）の現在値を直接変数として参照・演算し、結果を別のデバイスへ即時反映します。
- **Web UI & REST API連携**: ブラウザ上のエディタやREST APIを通じて、スクリプトの作成・検証・開始・一時停止・停止が可能です。

---

## 2. スクリプトの基本構造 (File Structure)

スクリプトはYAML形式で記述します。単一のスクリプト定義、または `scripts` 配列内に複数スクリプトを定義できます。

### 単一スクリプト例
```yaml
name: simple_counter
type: periodic
interval_ms: 1000
actions:
  - target: D100
    expr: D100 + 1
```

### 複数スクリプト例
```yaml
scripts:
  - name: generator
    type: periodic
    interval_ms: 500
    actions:
      - target: D0
        expr: int(50 * sin(t) + 50)
  - name: interlock
    type: conditional
    interval_ms: 200
    conditions:
      - when: D0 > 80
        actions:
          - target: M0
            value: 1
      - when: D0 <= 80
        actions:
          - target: M0
            value: 0
```

---

## 3. スクリプトタイプ別リファレンス (Script Types)

### 3.1 周期実行 (`periodic`)
指定したインターバル（`interval_ms`）ごとにアクションリスト（`actions`）を実行します。

#### キー仕様
| キー | 型 | 必須 | デフォルト値 | 説明 |
|---|---|---|---|---|
| `type` | string | **必須** | - | `"periodic"` を指定 |
| `interval_ms` | number | **必須** | - | 実行周期（ミリ秒、正の数値） |
| `actions` | list | **必須** | - | 実行するアクションのリスト |
| `name` | string | 任意 | `"unnamed"` | スクリプトの識別名 |

- `target`: 書き込み先デバイス名（例: `D100`, `M0`, `Y10`）
- `value`: 直接設定する値。通常のワード書き込みは数値、型付きASCIIは文字列
- `expr`: 評価式文字列（`value` または `expr` のいずれか一方を指定）
- `data_type`: 任意の型付きワード書き込み（`dword`, `long`, `float32`, `ascii`）
- `length`: `data_type: ascii` の固定長（文字数）。不足分はNULで埋める

型付き値はリトルエンディアンで連続する16ビットワードへ格納します。`dword` は符号なし32ビット整数、`long` は符号付き32ビット整数、`float32` はIEEE 754単精度浮動小数点です。`ascii` は1文字目を下位バイトへ格納し、奇数バイトの末尾はNULで補います。型付き値はワードデバイスにのみ指定できます。

```yaml
name: typed_values
type: sequence
steps:
  - wait_ms: 0
    actions:
      - target: D300
        value: 100000
        data_type: dword
      - target: D310
        value: -12.5
        data_type: float32
      - target: D320
        value: PLC
        data_type: ascii
        length: 8
```
#### 実例
```yaml
name: periodic_sensor
type: periodic
interval_ms: 500
actions:
  - target: D100
    expr: int(50 * sin(t) + 50)
  - target: M0
    expr: 1 if D100 > 75 else 0
```

---

### 3.2 条件分岐 (`conditional`)
指定したインターバルごとに条件リスト（`conditions`）の式（`when`）を評価し、成立した場合に該当アクションを実行します。

#### キー仕様
| キー | 型 | 必須 | デフォルト値 | 説明 |
|---|---|---|---|---|
| `type` | string | **必須** | - | `"conditional"` を指定 |
| `interval_ms` | number | **必須** | - | 評価周期（ミリ秒、正の数値） |
| `conditions` | list | **必須** | - | 条件定義のリスト |
| `name` | string | 任意 | `"unnamed"` | スクリプトの識別名 |

#### 条件定義のキー仕様
- `when`: 評価する条件式（文字列、真偽値または比較式）
- `actions`: 条件成立時に実行するアクションリスト

#### 実例
```yaml
name: tank_level_interlock
type: conditional
interval_ms: 200
conditions:
  - when: D100 >= 90
    actions:
      - target: M10
        value: 1
      - target: Y0
        value: 0
  - when: D100 < 90
    actions:
      - target: M10
        value: 0
```

---

### 3.3 シーケンス順序制御 (`sequence`)
複数のステップ（`steps`）を定義し、待機時間（`wait_ms`）を経て順次アクションを実行します。

#### キー仕様
| キー | 型 | 必須 | デフォルト値 | 説明 |
|---|---|---|---|---|
| `type` | string | **必須** | - | `"sequence"` を指定 |
| `steps` | list | **必須** | - | シーケンスステップのリスト |
| `name` | string | 任意 | `"unnamed"` | スクリプトの識別名 |
| `loop` | boolean | 任意 | `false` | 全ステップ終了後に先頭から繰り返すか |

#### ステップ定義のキー仕様
- `wait_ms`: ステップの待機時間（ミリ秒、0以上の数値）
- `actions`: ステップ実行時に適用するアクションリスト

#### 実例 (信号機サイクル)
```yaml
name: traffic_light_sequence
type: sequence
loop: true
steps:
  - wait_ms: 3000
    actions:
      - target: Y0
        value: 1
      - target: Y1
        value: 0
      - target: Y2
        value: 0
  - wait_ms: 1000
    actions:
      - target: Y0
        value: 0
      - target: Y1
        value: 1
      - target: Y2
        value: 0
  - wait_ms: 3000
    actions:
      - target: Y0
        value: 0
      - target: Y1
        value: 0
      - target: Y2
        value: 1
```

---

### 3.4 ランプ変化 (`ramp`)
指定したデバイスの値を初期値（`start_value`）から目標値（`end_value`）まで、指定した期間（`duration_ms`）で線形に変化させます。

#### キー仕様
| キー | 型 | 必須 | デフォルト値 | 説明 |
|---|---|---|---|---|
| `type` | string | **必須** | - | `"ramp"` を指定 |
| `target` | string | **必須** | - | 変化させるデバイス名（例: `D200`） |
| `start_value` | number | **必須** | - | 開始値 |
| `end_value` | number | **必須** | - | 終了値 |
| `duration_ms` | number | **必須** | - | 変化にかける総時間（ミリ秒、正の数値） |
| `name` | string | 任意 | `"unnamed"` | スクリプトの識別名 |
| `step_ms` | number | 任意 | `100` | 値更新のステップ間隔（ミリ秒） |
| `loop` | boolean | 任意 | `false` | 目標値到達後に開始値から繰り返すか |

#### 実例
```yaml
name: ramp_generator
type: ramp
target: D200
start_value: 0
end_value: 1000
duration_ms: 10000
loop: true
```

---

## 4. 式評価器リファレンス (Expression Evaluator)

`expr` や `when` で利用可能な式言語の仕様です。

### 4.1 組み込み変数 (Built-in Variables)
| 変数名 | 型 | 説明 |
|---|---|---|
| `t` | float | スクリプト起動時からの累積経過秒数 |
| `dt` | float | 前回の実行からの経過秒数 |
| `tick` | int | 実行カウンタ（呼び出しごとに 1 増加） |

### 4.2 デバイス値参照
任意のPLCデバイス名を式の中でそのまま変数として使用できます。
- ビットデバイス（`X`, `Y`, `M`, `L`, `B` 等）: `0` または `1`
- ワードデバイス（`D`, `W`, `R`, `ZR` 等）: 16進整数値（符号なし 0〜65535）

```yaml
name: device_ref_example
type: periodic
interval_ms: 100
actions:
  - target: D100
    expr: D100 + 1
```

### 4.3 組み込み関数 (Built-in Functions)
| 関数名 | 引数 | 説明 |
|---|---|---|
| `sin(x)` | x: rad | 正弦関数 |
| `cos(x)` | x: rad | 余弦関数 |
| `abs(x)` | x: number | 絶対値 |
| `min(a, b, ...)` | 2つ以上の値 | 最小値 |
| `max(a, b, ...)` | 2つ以上の値 | 最大値 |
| `floor(x)` | x: float | 切り捨て（整数値） |
| `ceil(x)` | x: float | 切り上げ（整数値） |
| `int(x)` | x: number | 整数変換（小数点切り捨て） |
| `clamp(x, lo, hi)` | x, lo, hi | `lo` 以上 `hi` 以下の範囲に収める |
| `random()` | なし | 0.0 以上 1.0 未満の浮動小数点乱数 |
| `randint(a, b)` | a, b: int | `a` 以上 `b` 以下の整数乱数 |
| `square(t, period)` | t, period | 周期 `period` の矩形波（0.0 または 1.0） |
| `triangle(t, period)` | t, period | 周期 `period` の三角波（0.0 〜 1.0） |
| `sawtooth(t, period)` | t, period | 周期 `period` のノコギリ波（0.0 〜 1.0） |

### 4.4 演算子 (Operators)
- **算術演算**: `+`, `-`, `*`, `/`, `//` (切り捨て除算), `%` (剰余), `**` (べき乗, 最大指数1000)
- **比較演算**: `==`, `!=`, `<`, `<=`, `>`, `>=`
- **論理演算**: `and`, `or`, `not`
- **三項演算**: `true_value if condition else false_value`

### 4.5 禁止構文とセキュリティ制約
スクリプトエンジンは厳密なASTホワイトリスト検査を実施します。以下を含む構文はバリデーション時に拒否されます:
- `import`, `__import__`, `sys`, `os` などのモジュールインポート
- `eval()`, `exec()`, `compile()`, `open()` などの組み込み危険関数
- オブジェクトの属性アクセス（例: `x.__class__`, `x.foo`）
- 無限ループ・巨大指数（`**` の指数が 1000 を超える計算はタイムアウト保護）
- 1回の式評価あたり 0.05 秒を超える処理は自動的に中断されます

---

## 5. スクリプトの実行・管理 (Execution & Operations)

### 5.1 Web UIからの操作
1. ナビゲーションバーの「スクリプト」タブを開きます。
2. エディタにYAMLを記述するか、**「テンプレート」ドロップダウン**からプリセットを選択して「テンプレート読込」をクリックします。
3. **「Validate」**: 構文および式の安全性を即時チェックします。
4. **「Start」**: スクリプトの実行を開始します。ステータスが `running` に遷移します。
5. **「Pause」**: スクリプトの更新を一時停止します（`paused`）。再度「Start」で再開できます。
6. **「Stop」**: スクリプトを停止します（`stopped`）。
7. **「Save」**: 記述したスクリプトを名前を付けて保存します。

### 5.2 REST APIからの操作
| メソッド | エンドポイント | 説明 |
|---|---|---|
| `GET` | `/api/scripts` | 保存済みユーザースクリプト一覧を取得 |
| `GET` | `/api/scripts/{name}` | 指定スクリプトの内容を取得 |
| `PUT` | `/api/scripts/{name}` | スクリプトを保存（JSON: `{"content": "..."}`） |
| `GET` | `/api/scripts/templates` | プリセットテンプレート一覧を取得 |
| `GET` | `/api/scripts/templates/{name}` | テンプレート内容を取得 |
| `POST` | `/api/scripts/validate` | スクリプトの構文・式を検証（JSON: `{"content": "..."}`） |
| `GET` | `/api/scripts/{name}/status` | 実行状態（`running`, `paused`, `stopped`）を取得 |
| `POST` | `/api/scripts/{name}/start` | スクリプトを開始 |
| `POST` | `/api/scripts/{name}/pause` | スクリプトを一時停止 |
| `POST` | `/api/scripts/{name}/stop` | スクリプトを停止 |
