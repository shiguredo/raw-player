# raw-player

[![PyPI](https://img.shields.io/pypi/v/raw-player)](https://pypi.org/project/raw-player/)
[![image](https://img.shields.io/pypi/pyversions/raw-player.svg)](https://pypi.python.org/pypi/raw-player)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Actions status](https://github.com/shiguredo/raw-player/workflows/wheel/badge.svg)](https://github.com/shiguredo/raw-player/actions)

## About Shiguredo's open source software

We will not respond to PRs or issues that have not been discussed on Discord. Also, Discord is only available in Japanese.

Please read <https://github.com/shiguredo/oss/blob/master/README.en.md> before use.

## 時雨堂のオープンソースソフトウェアについて

利用前に <https://github.com/shiguredo/oss> をお読みください。

## raw-player について

> [!WARNING]
> raw-player は破壊的変更を伴う可能性のある開発段階のソフトウェアです。
> そのため、 API は予告なく変更される可能性があります。

[numpy.ndarray](https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html) 形式で渡された生の映像・音声データを再生する Python ライブラリです。

PCM / I420 / NV12 / YUY2 / RGBA / BGRA データを PTS (Presentation Timestamp) に基づいて音声と映像を同期しながら再生します。

<https://github.com/user-attachments/assets/cdbb5b95-dbb7-4088-a842-0c66830e2a25>

## 特徴

- 生の音声/映像入力データをそのまま再生できる
- 入力データに numpy.ndarray を採用
- 音声フォーマットは PCM (int16 / float32) に対応
- 映像フォーマットは I420 (YUV420P) / NV12 / YUY2 / RGBA / BGRA に対応
- PTS ベース音声をマスタークロックとした映像同期機能
- GPU レンダリング
  - macOS: Metal
  - Windows: Vulkan / Direct3D 12
  - Linux: Vulkan

## 対応プラットフォーム

- macOS 26 arm64
- macOS 15 arm64
- Ubuntu 24.04 x86_64
- Ubuntu 24.04 arm64
- Windows 11 x86_64

## 対応 Python

- 3.14
- 3.13
- 3.12

## インストール

```bash
uv add raw-player
```

## 使い方

### 音声再生

```python
import numpy as np
import raw_player as rp

player = rp.AudioPlayer()

# 440Hz のサイン波を生成
sample_rate = 48000
duration = 2.0
t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
mono = 0.3 * np.sin(2 * np.pi * 440.0 * t)

# ステレオに変換(shape: (frames, channels))
stereo = np.column_stack([mono, mono])

# PTS とサンプルレートを指定してキューに追加
player.enqueue_audio(stereo, pts_us=0, sample_rate=sample_rate)
player.play()
```

### I420 (YUV420P) 再生

```python
import numpy as np
import raw_player as rp

# ウィンドウサイズとタイトルを指定して作成
player = rp.VideoPlayer(width=1920, height=1080, title="I420 Player")

# Y, U, V プレーンを用意
# Y: (H, W), U: (H/2, W/2), V: (H/2, W/2)
y_plane = np.zeros((1080, 1920), dtype=np.uint8)
u_plane = np.zeros((540, 960), dtype=np.uint8)
v_plane = np.zeros((540, 960), dtype=np.uint8)

# PTS(マイクロ秒)を指定してキューに追加
player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)
player.play()

while player.is_open:
    # イベント処理とフレームレンダリング
    if not player.poll_events():
        break

player.close()
```

### NV12 再生

```python
import numpy as np
import raw_player as rp

player = rp.VideoPlayer(width=1920, height=1080, title="NV12 Player")

# Y プレーンと UV インターリーブプレーンを用意
# Y: (H, W), UV: (H/2, W)
y_plane = np.zeros((1080, 1920), dtype=np.uint8)
uv_plane = np.zeros((540, 1920), dtype=np.uint8)

# PTS(マイクロ秒)を指定してキューに追加
player.enqueue_video_nv12(y_plane, uv_plane, pts_us=0)
player.play()

while player.is_open:
    if not player.poll_events():
        break

player.close()
```

### YUY2 再生

```python
import numpy as np
import raw_player as rp

player = rp.VideoPlayer(width=1920, height=1080, title="YUY2 Player")

# YUY2: パックドフォーマット (H, W*2)
# Y0 U0 Y1 V0 Y2 U1 Y3 V1 ... の形式(2 ピクセルで 4 バイト)
yuy2_data = np.zeros((1080, 1920 * 2), dtype=np.uint8)

# PTS(マイクロ秒)を指定してキューに追加
player.enqueue_video_yuy2(yuy2_data, pts_us=0)
player.play()

while player.is_open:
    if not player.poll_events():
        break

player.close()
```

### RGBA 再生

```python
import numpy as np
import raw_player as rp

player = rp.VideoPlayer(width=1920, height=1080, title="RGBA Player")

# RGBA: (H, W, 4)
rgba_data = np.zeros((1080, 1920, 4), dtype=np.uint8)

# PTS(マイクロ秒)を指定してキューに追加
player.enqueue_video_rgba(rgba_data, pts_us=0)
player.play()

while player.is_open:
    if not player.poll_events():
        break

player.close()
```

### BGRA 再生

```python
import numpy as np
import raw_player as rp

player = rp.VideoPlayer(width=1920, height=1080, title="BGRA Player")

# BGRA: (H, W, 4)
bgra_data = np.zeros((1080, 1920, 4), dtype=np.uint8)

# PTS(マイクロ秒)を指定してキューに追加
player.enqueue_video_bgra(bgra_data, pts_us=0)
player.play()

while player.is_open:
    if not player.poll_events():
        break

player.close()
```

### PTS ベースの AV 同期再生

```python
import numpy as np
import raw_player as rp

# 映像と音声を統合したプレイヤー
player = rp.VideoPlayer(width=1920, height=1080, title="AV Sync Player")

# 映像フレームをキューに追加(I420 形式)
player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)

# 音声データをキューに追加
# pcm: int16 または float32、shape: (frames,) または (frames, channels)
player.enqueue_audio(audio_data, pts_us=0, sample_rate=48000)

player.play()

while player.is_open:
    if not player.poll_events():
        break
    # poll_events() が音声 PTS に基づいて適切なフレームを自動描画

player.close()
```

## API リファレンス

### AudioPlayer

独立した音声再生用クラス。

```python
player = AudioPlayer()
```

| メソッド | 説明 |
|----------|------|
| `enqueue_audio(pcm, pts_us, sample_rate)` | 音声データをキューに追加 |
| `play()` | 再生開始/再開 |
| `pause()` | 一時停止 |
| `stop()` | 停止してキューをクリア |
| `stats()` | 統計情報を取得 |

| プロパティ | 説明 |
|------------|------|
| `is_playing` | 再生中かどうか |
| `volume` | 音量(0.0〜1.0) |

#### enqueue_audio の引数

- `pcm`: 音声データ(int16 または float32 の numpy 配列)
  - 1D: `(frames,)` モノラル
  - 2D: `(frames, channels)` マルチチャンネル
- `pts_us`: PTS(マイクロ秒)
- `sample_rate`: サンプルレート(Hz)

### VideoPlayer

映像再生用クラス。音声も統合可能。

```python
player = VideoPlayer(width=960, height=540, title="Raw Player")
```

| メソッド | 説明 |
|----------|------|
| `enqueue_video_i420(y, u, v, pts_us)` | I420 フレームをキューに追加 |
| `enqueue_video_nv12(y, uv, pts_us)` | NV12 フレームをキューに追加 |
| `enqueue_video_yuy2(data, pts_us)` | YUY2 フレームをキューに追加 |
| `enqueue_video_rgba(data, pts_us)` | RGBA フレームをキューに追加 |
| `enqueue_video_bgra(data, pts_us)` | BGRA フレームをキューに追加 |
| `enqueue_audio(pcm, pts_us, sample_rate)` | 音声データをキューに追加 |
| `play()` | 再生開始 |
| `pause()` | 一時停止 |
| `stop()` | 停止してキューをクリア |
| `close()` | リソースを解放 |
| `poll_events()` | イベント処理とフレーム描画(閉じられたら False) |
| `set_key_callback(callback)` | キーイベントコールバックを設定 |
| `stats()` | 統計情報を取得 |

| プロパティ | 説明 |
|------------|------|
| `is_open` | ウィンドウが開いているか |
| `is_playing` | 再生中か |
| `width` | ウィンドウ幅 |
| `height` | ウィンドウ高さ |
| `title` | ウィンドウタイトル(読み書き可) |
| `renderer_name` | GPU レンダラー名(metal, vulkan など) |
| `volume` | 音量(0.0〜1.0) |

#### enqueue_video_i420 の引数

- `y`: Y プレーン(uint8、shape: `(H, W)`)
- `u`: U プレーン(uint8、shape: `(H/2, W/2)`)
- `v`: V プレーン(uint8、shape: `(H/2, W/2)`)
- `pts_us`: PTS(マイクロ秒)

#### enqueue_video_nv12 の引数

- `y`: Y プレーン(uint8、shape: `(H, W)`)
- `uv`: UV インターリーブプレーン(uint8、shape: `(H/2, W)`)
- `pts_us`: PTS(マイクロ秒)

#### enqueue_video_yuy2 の引数

- `data`: YUY2 パックドデータ(uint8、shape: `(H, W*2)`)
  - `Y0 U0 Y1 V0 Y2 U1 Y3 V1 ...` の形式(2 ピクセルで 4 バイト)
- `pts_us`: PTS(マイクロ秒)

#### enqueue_video_rgba の引数

- `data`: RGBA データ(uint8、shape: `(H, W, 4)`)
- `pts_us`: PTS(マイクロ秒)

#### enqueue_video_bgra の引数

- `data`: BGRA データ(uint8、shape: `(H, W, 4)`)
- `pts_us`: PTS(マイクロ秒)

#### stats() の戻り値

```python
{
  "video_queue_size": int,      # 映像キュー内のフレーム数
  "audio_queue_ms": float,      # 音声キューの長さ(ミリ秒)
  "dropped_frames": int,        # ドロップしたフレーム数
  "repeated_frames": int,       # 繰り返したフレーム数
  "video_pts_us": int,          # 最後に描画した映像の PTS
  "audio_pts_us": int,          # 現在の音声再生位置
  "sync_diff_us": int,          # 音声と映像の差
  "current_video_width": int,   # 現在の映像幅
  "current_video_height": int,  # 現在の映像高さ
  "current_fps": float,         # 現在の FPS
  "total_frames_enqueued": int, # エンキューしたフレーム総数
  "total_frames_rendered": int, # レンダリングしたフレーム総数
  "video_buffer_ms": float,     # 映像バッファ時間(ミリ秒)
  "elapsed_time_ms": float,     # 経過時間(ミリ秒)
  "video_bitrate_kbps": float,  # 映像ビットレート(kbps)
}
```

### モジュール関数

システム情報を取得するためのモジュールレベル関数。

| 関数 | 説明 |
|------|------|
| `get_version()` | SDL のバージョン文字列を取得 |
| `get_audio_driver()` | 現在の音声ドライバー名を取得 |
| `get_video_driver()` | 現在の映像ドライバー名を取得 |
| `get_gpu_driver()` | プライマリ GPU ドライバー名を取得(metal, vulkan, d3d12 など) |
| `get_num_gpu_drivers()` | 利用可能な GPU ドライバーの数を取得 |
| `get_all_gpu_drivers()` | 利用可能な全ての GPU ドライバー名をリストで取得 |

#### 使用例

```python
from raw_player import (
    get_version,
    get_audio_driver,
    get_video_driver,
    get_gpu_driver,
    get_all_gpu_drivers,
)

# SDL バージョンを表示
print(f"SDL Version: {get_version()}")

# ドライバー情報を表示
print(f"Audio Driver: {get_audio_driver()}")
print(f"Video Driver: {get_video_driver()}")
print(f"GPU Driver: {get_gpu_driver()}")

# 利用可能な全ての GPU ドライバーを表示
print(f"Available GPU Drivers: {get_all_gpu_drivers()}")
```

## Simple DirectMedia Layer ライセンス

Zlib license

<https://github.com/libsdl-org/SDL/blob/main/LICENSE.txt>

```text
Copyright (C) 1997-2025 Sam Lantinga <slouken@libsdl.org>
  
This software is provided 'as-is', without any express or implied
warranty.  In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:
  
1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would be
   appreciated but is not required. 
2. Altered source versions must be plainly marked as such, and must not be
   misrepresented as being the original software.
3. This notice may not be removed or altered from any source distribution.

```

## raw-player ライセンス

Apache License 2.0

```text
Copyright 2025-2025, Shiguredo Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
