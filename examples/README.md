# サンプル

raw-player の使用例です。

## 共通操作

- `ESC` または `q` キーで終了
- `s` キーで統計情報を表示

## ビルドと依存ライブラリのインストール

```bash
make develop
```

## blend2d_player.py

[Blend2D](https://blend2d.com/) でアニメーションを生成し、raw-player で表示するサンプルです。

### 依存

- [blend2d-py](https://github.com/shiguredo/blend2d-py)
- [webcodecs-py](https://github.com/shiguredo/webcodecs-py)

### 実行

```bash
# 生データ(エンコードなし)
uv run python examples/blend2d_player.py

# H.264 エンコード/デコード
uv run python examples/blend2d_player.py --video-codec-type H264

# H.265 エンコード/デコード
uv run python examples/blend2d_player.py --video-codec-type H265

# 解像度とフレームレートを指定
uv run python examples/blend2d_player.py --resolution 1280x720 --fps 30
```

### オプション

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--duration` | 再生時間(秒) | 10.0 |
| `--fps` | フレームレート (30, 60, 120) | 60 |
| `--video-codec-type` | コーデック (AV1, VP8, VP9, H264, H265) | なし |
| `--video-bitrate` | ビットレート (kbps) | 8000 |
| `--resolution` | 解像度 (WIDTHxHEIGHT) | 1920x1080 |
| `--hide-info` | 情報表示を非表示 | なし |

## camera_player.py

uvc-py でカメラ映像を取得し、raw-player で表示するサンプルです。

### 依存

- [uvc-py](https://github.com/shiguredo/uvc-py)
- [webcodecs-py](https://github.com/shiguredo/webcodecs-py)

### 実行

```bash
# 生データ(エンコードなし)
uv run python examples/camera_player.py

# H.264 エンコード/デコード
uv run python examples/camera_player.py --video-codec-type H264

# カメラ番号と解像度を指定
uv run python examples/camera_player.py --camera 0 --width 1920 --height 1080
```

### オプション

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--duration` | 再生時間(秒) | 10.0 |
| `--camera` | カメラデバイス番号 | 0 |
| `--width` | 映像幅 | 1280 |
| `--height` | 映像高さ | 720 |
| `--fps` | フレームレート | 30 |
| `--video-codec-type` | コーデック (AV1, H264, H265, VP8, VP9) | なし |
| `--video-bitrate` | ビットレート (kbps) | 8000 |
| `--capture-format` | キャプチャフォーマット (NV12, YUY2) | NV12 |
| `--flip-horizontal` | 左右反転 | なし |
| `--flip-vertical` | 上下反転 | なし |
| `--native-buffer` | ネイティブバッファを使用 (macOS のみ) | なし |

## av_player.py

カメラ映像とマイク音声を同時に再生するサンプルです。

### 依存

- [uvc-py](https://github.com/shiguredo/uvc-py)
- [portaudio-py](https://github.com/shiguredo/portaudio-py)

### 実行

```bash
# デバイス一覧を表示
uv run python examples/av_player.py --list-devices

# カメラとマイクを同時に再生
uv run python examples/av_player.py

# 解像度とフレームレートを指定
uv run python examples/av_player.py --resolution 1080p --fps 30

# デバイスを指定
uv run python examples/av_player.py --video-device 0 --audio-device 1
```

### オプション

| オプション | 説明 | デフォルト |
|------------|------|------------|
| `--video-device` | 映像デバイス (インデックス、ID、または名前) | 自動選択 |
| `--audio-device` | 音声入力デバイスインデックス | 自動選択 |
| `--resolution` | 解像度 (1080p, 720p, 480p, 4k, WIDTHxHEIGHT) | 720p |
| `--fps` | フレームレート | 30 |
| `--sample-rate` | 音声サンプルレート | 48000 |
| `--audio-channels` | 音声チャンネル数 | 1 |
| `--duration` | 再生時間(秒) | 無制限 |
| `--list-devices` | デバイス一覧を表示して終了 | なし |
| `--native-buffer` | CVPixelBuffer を直接使用 (macOS のみ) | なし |
