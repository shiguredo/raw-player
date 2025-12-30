"""Blend2D アニメーションテスト

blend2d-py でうねうね動くアニメーションを生成し、
webcodecs-py でエンコード/デコードして、
raw-player で表示します。
"""

import argparse
import math
import time
from collections import deque

import numpy as np
from blend2d import CompOp, Context, Font, FontFace, Image
from webcodecs import (
    EncodedVideoChunk,
    HardwareAccelerationEngine,
    LatencyMode,
    VideoDecoder,
    VideoDecoderConfig,
    VideoEncoder,
    VideoEncoderConfig,
    VideoFrame,
    VideoPixelFormat,
)

from raw_player import VideoPlayer, get_gpu_driver, get_version

# 定数
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 60

# アニメーション用定数
NUM_BALLS = 8
NUM_WAVES = 5


def bgra_to_i420(bgra: np.ndarray, width: int, height: int, timestamp_us: int = 0):
    """
    BGRA (H, W, 4) を I420 形式に変換(VideoFrame.copy_to を使用)

    Args:
        bgra: BGRA 画像データ
        width: 画像幅
        height: 画像高さ
        timestamp_us: タイムスタンプ(マイクロ秒)

    戻り値:
        I420 形式の VideoFrame
    """
    # BGRA で VideoFrame を作成
    bgra_frame = VideoFrame(
        bgra.flatten(),
        {
            "format": VideoPixelFormat.BGRA,
            "coded_width": width,
            "coded_height": height,
            "timestamp": timestamp_us,
        },
    )

    # I420 用のバッファを確保
    i420_size = bgra_frame.allocation_size({"format": VideoPixelFormat.I420})
    i420_data = np.zeros(i420_size, dtype=np.uint8)

    # I420 フォーマットでコピー
    bgra_frame.copy_to(i420_data, {"format": VideoPixelFormat.I420})
    bgra_frame.close()

    # VideoFrame を I420 で作成
    return VideoFrame(
        i420_data,
        {
            "format": VideoPixelFormat.I420,
            "coded_width": width,
            "coded_height": height,
            "timestamp": timestamp_us,
        },
    )


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """HSV を RGB に変換 (h: 0-360, s: 0-1, v: 0-1)"""
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def generate_frame(
    img: Image,
    font_large: Font,
    font_small: Font,
    frame_number: int,
    width: int,
    height: int,
    actual_fps: float,
    target_fps: int,
    codec_type: str | None = None,
) -> np.ndarray:
    """
    blend2d でアニメーションフレームを生成

    戻り値:
        BGRA numpy 配列 (H, W, 4)
    """
    t = frame_number / target_fps  # 経過時間(秒)

    with Context(img) as ctx:
        # 合成モードを設定
        ctx.set_comp_op(CompOp.SRC_COPY)

        # 背景色を時間で変化させる(暗めのグラデーション)
        bg_hue = (t * 20) % 360
        bg_r, bg_g, bg_b = hsv_to_rgb(bg_hue, 0.3, 0.15)
        ctx.set_fill_style_rgba(bg_r, bg_g, bg_b, 255)
        ctx.fill_all()

        # ウェーブパターンを描画
        ctx.set_comp_op(CompOp.SRC_OVER)
        for wave_idx in range(NUM_WAVES):
            wave_offset = wave_idx * 0.5
            wave_amplitude = 50 + wave_idx * 20
            wave_freq = 0.008 + wave_idx * 0.002
            wave_speed = 2.0 + wave_idx * 0.3
            wave_y_base = height * 0.3 + wave_idx * 80

            # ウェーブの色(虹色サイクル)
            wave_hue = (t * 60 + wave_idx * 50) % 360
            wr, wg, wb = hsv_to_rgb(wave_hue, 0.8, 0.9)

            # ウェーブを描画(複数の円で構成)
            for x in range(0, width, 20):
                y = wave_y_base + wave_amplitude * math.sin(
                    wave_freq * x + t * wave_speed + wave_offset
                )
                radius = 8 + 4 * math.sin(t * 3 + x * 0.01)
                ctx.set_fill_style_rgba(wr, wg, wb, 150)
                ctx.fill_circle(x, y, radius)

        # バウンドするボールを描画
        for ball_idx in range(NUM_BALLS):
            # 各ボールの位置を計算(リサージュ曲線風)
            freq_x = 0.5 + ball_idx * 0.15
            freq_y = 0.7 + ball_idx * 0.12
            phase_x = ball_idx * math.pi / 4
            phase_y = ball_idx * math.pi / 3

            ball_x = width * 0.5 + (width * 0.35) * math.sin(t * freq_x + phase_x)
            ball_y = height * 0.5 + (height * 0.3) * math.sin(t * freq_y + phase_y)

            # ボールの大きさを脈動させる
            ball_radius = 30 + 15 * math.sin(t * 4 + ball_idx)

            # ボールの色(虹色)
            ball_hue = (ball_idx * 45 + t * 100) % 360
            br, bg, bb = hsv_to_rgb(ball_hue, 1.0, 1.0)
            ctx.set_fill_style_rgba(br, bg, bb, 200)
            ctx.fill_circle(ball_x, ball_y, ball_radius)

            # 光沢効果(小さい白い円)
            ctx.set_fill_style_rgba(255, 255, 255, 100)
            ctx.fill_circle(
                ball_x - ball_radius * 0.3,
                ball_y - ball_radius * 0.3,
                ball_radius * 0.3,
            )

        # 回転する多角形パターン(中央)
        center_x = width * 0.5
        center_y = height * 0.5
        num_shapes = 6
        for shape_idx in range(num_shapes):
            angle = t * (1 + shape_idx * 0.2) + shape_idx * math.pi / 3
            dist = 150 + 50 * math.sin(t * 2 + shape_idx)
            shape_x = center_x + dist * math.cos(angle)
            shape_y = center_y + dist * math.sin(angle)

            shape_hue = (shape_idx * 60 + t * 80) % 360
            sr, sg, sb = hsv_to_rgb(shape_hue, 0.9, 0.95)

            # 円を描画
            size = 25 + 15 * math.sin(t * 3 + shape_idx)
            ctx.set_fill_style_rgba(sr, sg, sb, 180)
            ctx.fill_circle(shape_x, shape_y, size)

        # 経過時間をミリ秒で大きく表示(白、影付き)
        elapsed_ms = int(t * 1000)
        time_text = f"{elapsed_ms:08d} ms"
        text_x = width * 0.5 - 200
        text_y = height * 0.85

        # 影
        ctx.set_fill_style_rgba(0, 0, 0, 200)
        ctx.fill_utf8_text(text_x + 3, text_y + 3, font_large, time_text)
        # 本体
        ctx.set_fill_style_rgba(255, 255, 255, 255)
        ctx.fill_utf8_text(text_x, text_y, font_large, time_text)

        # 情報表示(左上)
        ctx.set_fill_style_rgba(255, 255, 255, 200)
        codec_text = f"{codec_type} -> I420" if codec_type else "RAW BGRA"
        info_text = f"{width}x{height} | {target_fps} FPS | {codec_text}"
        ctx.fill_utf8_text(30, 50, font_small, info_text)

        # フレーム番号(左上)
        ctx.set_fill_style_rgba(200, 200, 200, 255)
        frame_text = f"Frame: {frame_number:06d}"
        ctx.fill_utf8_text(30, 95, font_small, frame_text)

        # 実際の FPS(左上、緑)
        ctx.set_fill_style_rgba(150, 255, 150, 255)
        fps_text = f"FPS: {actual_fps:.1f}"
        ctx.fill_utf8_text(30, 140, font_small, fps_text)

    return img.asarray()


def main():
    """メインエントリポイント"""
    parser = argparse.ArgumentParser(description="Blend2D アニメーションテスト")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="再生時間(秒)。デフォルト: 10.0",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        choices=[30, 60, 120],
        help="フレームレート (30, 60, 120)。デフォルト: 60",
    )
    parser.add_argument(
        "--video-codec-type",
        type=str,
        default=None,
        choices=["AV1", "VP8", "VP9", "H264", "H265"],
        help="ビデオコーデック。指定時のみエンコード/デコードを行う",
    )
    parser.add_argument(
        "--video-bitrate",
        type=int,
        default=8000,
        help="ビットレート (kbps)。デフォルト: 8000",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default=f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
        help=f"解像度 (WIDTHxHEIGHT)。デフォルト: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
    )
    args = parser.parse_args()

    # 解像度をパース
    try:
        width, height = map(int, args.resolution.split("x"))
        if width <= 0 or height <= 0:
            raise ValueError
        # 2の倍数でなければ警告(I420形式の制約)
        if width % 2 != 0 or height % 2 != 0:
            print(f"警告: 解像度は2の倍数を推奨します(現在: {width}x{height})")
            width = width // 2 * 2
            height = height // 2 * 2
            print(f"自動調整: {width}x{height}")
    except ValueError:
        print(f"エラー: 無効な解像度形式: {args.resolution}")
        print("形式: WIDTHxHEIGHT (例: 1920x1080)")
        return
    fps = args.fps

    # コーデック設定
    codec_map = {
        "AV1": "av01.0.08M.08",
        "VP8": "vp8",
        "VP9": "vp09.00.10.08",  # Profile 0, Level 1.0, 8-bit
        "H264": "avc1.640032",  # High Profile, Level 5.0 (1080p60対応)
        "H265": "hvc1.1.6.L93.B0",  # Main Profile, Level 3.1
    }
    codec_string = codec_map.get(args.video_codec_type, "") if args.video_codec_type else ""
    bitrate = args.video_bitrate * 1000  # kbps -> bps

    total_frames = int(args.duration * fps)

    mode_str = "with webcodecs-py" if args.video_codec_type else "BGRA direct"
    print(f"Blend2D アニメーションテスト ({mode_str})")
    print(f"SDL Version: {get_version()}")
    print(f"GPU Driver: {get_gpu_driver()}")
    print(f"FPS: {fps}")
    print(f"Duration: {args.duration}s ({total_frames} frames)")
    print()

    # blend2d 画像を初期化(フレーム間で再利用)
    img = Image(width, height)

    # フォントをロード
    face = FontFace()
    face.create_from_file("/System/Library/Fonts/Helvetica.ttc")
    font_large = Font(face, 72.0)  # フレーム番号用
    font_small = Font(face, 32.0)  # 情報用

    # webcodecs 用の変数
    encoder = None
    decoder = None
    encoded_chunks: deque[EncodedVideoChunk] = deque()
    decoded_frames: deque[VideoFrame] = deque()

    if args.video_codec_type:
        # エンコーダのコールバック
        def on_encode_output(chunk: EncodedVideoChunk, metadata=None):
            encoded_chunks.append(chunk)

        def on_encode_error(error: str):
            print(f"Encode error: {error}")

        # デコーダのコールバック
        def on_decode_output(frame: VideoFrame):
            decoded_frames.append(frame)

        def on_decode_error(error: str):
            print(f"Decode error: {error}")

        # エンコーダを初期化
        encoder = VideoEncoder(on_encode_output, on_encode_error)
        encoder_config: VideoEncoderConfig = {
            "codec": codec_string,
            "width": width,
            "height": height,
            "bitrate": bitrate,
            "framerate": float(fps),
            "latency_mode": LatencyMode.REALTIME,
        }
        # H264/H265 はハードウェアアクセラレーションと Annex B フォーマット
        if args.video_codec_type == "H264":
            encoder_config["hardware_acceleration_engine"] = (
                HardwareAccelerationEngine.APPLE_VIDEO_TOOLBOX
            )
            encoder_config["avc"] = {"format": "annexb"}
        elif args.video_codec_type == "H265":
            encoder_config["hardware_acceleration_engine"] = (
                HardwareAccelerationEngine.APPLE_VIDEO_TOOLBOX
            )
            encoder_config["hevc"] = {"format": "annexb"}
        encoder.configure(encoder_config)

        # デコーダを初期化
        decoder = VideoDecoder(on_decode_output, on_decode_error)
        # Annex B フォーマットでは description なしで設定可能
        decoder_config: VideoDecoderConfig = {
            "codec": codec_string,
            "coded_width": width,
            "coded_height": height,
        }
        decoder.configure(decoder_config)

    # raw-player を初期化(新 API)
    title = (
        "Blend2D Animation Test (webcodecs)"
        if args.video_codec_type
        else "Blend2D Animation Test (raw)"
    )
    player = VideoPlayer(width=width, height=height, title=title)

    # キーコールバックを設定(ESC または q で終了)
    def on_key(key: int) -> bool:
        # ESC (27) または q (113) で終了
        if key == 27 or key == 113:
            return False
        return True

    player.set_key_callback(on_key)
    player.play()

    print(f"GPU Renderer: {player.renderer_name}")
    if args.video_codec_type:
        print(f"Encoder: {args.video_codec_type} ({codec_string})")
        print(f"Bitrate: {args.video_bitrate} kbps")
    else:
        print("Mode: BGRA direct (no conversion, no encode/decode)")
    print("ESC または q キーで終了...")
    print()

    frame_number = 0
    rendered_frames = 0
    start_time = time.perf_counter()

    # 統計用
    generate_times: list[float] = []
    convert_times: list[float] = []
    encode_times: list[float] = []
    decode_times: list[float] = []

    # フレームサイズ統計用
    raw_frame_sizes: list[int] = []  # 生データ (I420)
    encoded_frame_sizes: list[int] = []  # エンコード後
    decoded_frame_sizes: list[int] = []  # デコード後

    # フレーム生成のペーシング用
    frame_interval = 1.0 / fps  # フレーム間隔(秒)
    next_frame_time = time.perf_counter()

    try:
        while player.is_open and frame_number < total_frames:
            # SDL イベントを処理(これでフレームもレンダリングされる)
            if not player.poll_events():
                break

            # 次のフレーム時刻まで待機(FPS に合わせてペーシング)
            now = time.perf_counter()
            if now < next_frame_time:
                time.sleep(max(0, next_frame_time - now))

            # 次のフレーム時刻を更新
            next_frame_time += frame_interval

            # 現在の FPS を計算
            total_elapsed = time.perf_counter() - start_time
            current_fps = frame_number / total_elapsed if total_elapsed > 0 else 0

            # フレームを生成 (blend2d)
            generate_start = time.perf_counter()
            bgra = generate_frame(
                img,
                font_large,
                font_small,
                frame_number,
                width,
                height,
                current_fps,
                fps,
                args.video_codec_type,
            )
            generate_time = time.perf_counter() - generate_start
            generate_times.append(generate_time)

            # PTS を計算
            pts_us = int(frame_number * 1_000_000 / fps)

            if encoder and decoder:
                # BGRA → I420 変換
                convert_start = time.perf_counter()
                video_frame = bgra_to_i420(bgra, width, height, pts_us)
                convert_time = time.perf_counter() - convert_start
                convert_times.append(convert_time)

                # エンコード
                encode_start = time.perf_counter()
                is_keyframe = frame_number % (fps * 2) == 0  # 2秒ごとにキーフレーム
                encoder.encode(video_frame, {"key_frame": is_keyframe})
                video_frame.close()
                encode_time = time.perf_counter() - encode_start
                encode_times.append(encode_time)

                # エンコードされたチャンクをデコード
                decode_start = time.perf_counter()
                while encoded_chunks:
                    chunk = encoded_chunks.popleft()
                    encoded_frame_sizes.append(chunk.byte_length)
                    decoder.decode(chunk)
                decode_time = time.perf_counter() - decode_start
                decode_times.append(decode_time)

                # デコードされたフレームを enqueue
                while decoded_frames:
                    decoded_frame = decoded_frames.popleft()
                    # フォーマットに応じて enqueue
                    if decoded_frame.format == VideoPixelFormat.NV12:
                        # NV12: Y プレーン (plane 0) + UV インターリーブ (plane 1)
                        y_data = decoded_frame.plane(0)
                        uv_data = decoded_frame.plane(1)
                        decoded_frame_sizes.append(y_data.nbytes + uv_data.nbytes)
                        player.enqueue_video_nv12(y_data, uv_data, decoded_frame.timestamp)
                    else:
                        # I420: Y, U, V プレーン
                        y_plane, u_plane, v_plane = decoded_frame.planes()
                        decoded_frame_sizes.append(y_plane.nbytes + u_plane.nbytes + v_plane.nbytes)
                        player.enqueue_video_i420(
                            y_plane, u_plane, v_plane, decoded_frame.timestamp
                        )
                    decoded_frame.close()
                    rendered_frames += 1
            else:
                # 直接レンダリング(BGRA をそのまま使用)
                raw_frame_sizes.append(bgra.nbytes)

                # enqueue(変換なし)
                player.enqueue_video_bgra(bgra, pts_us)
                rendered_frames += 1

            frame_number += 1

            if frame_number % fps == 0:
                avg_generate = sum(generate_times[-60:]) / min(60, len(generate_times))
                total_elapsed = time.perf_counter() - start_time
                actual_fps = frame_number / total_elapsed
                stats = player.stats()
                if encoder and decoder:
                    avg_convert = sum(convert_times[-60:]) / min(60, len(convert_times))
                    avg_encode = sum(encode_times[-60:]) / min(60, len(encode_times))
                    avg_decode = sum(decode_times[-60:]) / min(60, len(decode_times))
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"gen={avg_generate * 1000:.1f}ms, "
                        f"conv={avg_convert * 1000:.1f}ms, "
                        f"enc={avg_encode * 1_000_000:.0f}us, "
                        f"dec={avg_decode * 1_000_000:.0f}us, "
                        f"queue={stats['video_queue_size']}, "
                        f"drop={stats['dropped_frames']}"
                    )
                else:
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"gen={avg_generate * 1000:.1f}ms, "
                        f"queue={stats['video_queue_size']}, "
                        f"drop={stats['dropped_frames']}"
                    )

    except KeyboardInterrupt:
        print("\n中断されました")

    # webcodecs 使用時はフラッシュしてクリーンアップ
    if encoder and decoder:
        encoder.flush()
        while encoded_chunks:
            chunk = encoded_chunks.popleft()
            decoder.decode(chunk)

        decoder.flush()
        while decoded_frames:
            decoded_frame = decoded_frames.popleft()
            if decoded_frame.format == VideoPixelFormat.NV12:
                y_data = decoded_frame.plane(0)
                uv_data = decoded_frame.plane(1)
                player.enqueue_video_nv12(y_data, uv_data, decoded_frame.timestamp)
            else:
                y_plane, u_plane, v_plane = decoded_frame.planes()
                player.enqueue_video_i420(y_plane, u_plane, v_plane, decoded_frame.timestamp)
            decoded_frame.close()
            rendered_frames += 1

        encoder.close()
        decoder.close()

    # 統計を表示
    total_time = time.perf_counter() - start_time
    if total_time > 0 and frame_number > 0:
        actual_fps = frame_number / total_time
        stats = player.stats()
        print()
        print(f"生成フレーム数: {frame_number}")
        print(f"レンダリングフレーム数: {rendered_frames}")
        print(f"平均 FPS: {actual_fps:.2f}")
        print(f"ドロップフレーム: {stats['dropped_frames']}")
        print(f"リピートフレーム: {stats['repeated_frames']}")
        if generate_times:
            print(f"平均生成時間: {sum(generate_times) / len(generate_times) * 1000:.2f}ms")
        if encoder and decoder and convert_times:
            print(f"平均変換時間: {sum(convert_times) / len(convert_times) * 1000:.2f}ms")
        if encoder and decoder:
            if encode_times:
                print(
                    f"平均エンコード時間: {sum(encode_times) / len(encode_times) * 1_000_000:.0f}us"
                )
            if decode_times:
                print(
                    f"平均デコード時間: {sum(decode_times) / len(decode_times) * 1_000_000:.0f}us"
                )
        # フレームサイズ統計
        print()
        if raw_frame_sizes:
            avg_raw = sum(raw_frame_sizes) / len(raw_frame_sizes)
            format_name = "I420" if encoder and decoder else "BGRA"
            print(f"平均生データサイズ ({format_name}): {avg_raw / 1024:.2f} KB")
        if encoder and decoder:
            if encoded_frame_sizes:
                avg_encoded = sum(encoded_frame_sizes) / len(encoded_frame_sizes)
                print(
                    f"平均エンコード後サイズ ({args.video_codec_type}): {avg_encoded / 1024:.2f} KB"
                )
            if decoded_frame_sizes:
                avg_decoded = sum(decoded_frame_sizes) / len(decoded_frame_sizes)
                print(f"平均デコード後サイズ (I420): {avg_decoded / 1024:.2f} KB")
            if raw_frame_sizes and encoded_frame_sizes:
                avg_raw = sum(raw_frame_sizes) / len(raw_frame_sizes)
                avg_encoded = sum(encoded_frame_sizes) / len(encoded_frame_sizes)
                compression_ratio = avg_raw / avg_encoded
                print(f"圧縮率: {compression_ratio:.1f}x ({avg_encoded / avg_raw * 100:.1f}%)")

    player.close()
    print("完了")


if __name__ == "__main__":
    main()
