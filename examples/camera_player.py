"""カメラ映像テスト

OpenCV でカメラ映像を取得し、
webcodecs-py でエンコード/デコードして、
raw-player で表示します。
"""

import argparse
import time
from collections import deque

import cv2
import numpy as np
from webcodecs import (
    EncodedVideoChunk,
    HardwareAccelerationEngine,
    LatencyMode,
    VideoDecoder,
    VideoEncoder,
    VideoEncoderConfig,
    VideoFrame,
    VideoPixelFormat,
)

from raw_player import VideoPlayer, get_gpu_driver, get_version

# デフォルト解像度
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30


def bgr_to_i420_planes(
    bgr: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    BGR (H, W, 3) を I420 の Y, U, V プレーンに変換

    戻り値:
        (Y, U, V) プレーンのタプル
        Y: (H, W), U: (H/2, W/2), V: (H/2, W/2)
    """
    height, width = bgr.shape[:2]
    # OpenCV の cvtColor で BGR -> YUV_I420 に変換
    i420 = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420)

    # I420 レイアウト: Y (H, W) + U (H/2, W/2) + V (H/2, W/2)
    y_size = width * height
    uv_size = (width // 2) * (height // 2)

    y_plane = i420[:height, :].reshape(height, width)
    u_plane = i420.flatten()[y_size : y_size + uv_size].reshape(height // 2, width // 2)
    v_plane = i420.flatten()[y_size + uv_size :].reshape(height // 2, width // 2)

    return y_plane, u_plane, v_plane


def draw_overlay(
    bgr_frame: np.ndarray,
    frame_number: int,
    width: int,
    height: int,
    fps: int,
    actual_fps: float,
    codec_type: str,
) -> np.ndarray:
    """
    フレームにオーバーレイ情報を描画 (OpenCV)

    Args:
        bgr_frame: BGR フレーム
        frame_number: フレーム番号
        width: 映像幅
        height: 映像高さ
        fps: 目標 FPS
        actual_fps: 実際の FPS
        codec_type: コーデック種別

    戻り値:
        オーバーレイが描画された BGR フレーム
    """
    # フォント設定
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.7
    thickness = 2
    color = (255, 255, 255)  # 白
    shadow_color = (0, 0, 0)  # 黒（影用）

    # 表示するテキスト
    lines = [
        f"{width}x{height} | {fps} FPS | {codec_type}",
        f"BGR -> I420 -> YUV420P",
        f"Frame: {frame_number:06d}",
        f"FPS: {actual_fps:.1f}",
    ]

    # テキストを描画
    y_offset = 30
    for line in lines:
        # 影を描画（読みやすくするため）
        cv2.putText(
            bgr_frame,
            line,
            (12, y_offset + 2),
            font,
            font_scale,
            shadow_color,
            thickness + 1,
        )
        # テキストを描画
        cv2.putText(bgr_frame, line, (10, y_offset), font, font_scale, color, thickness)
        y_offset += 30

    return bgr_frame


def main():
    """メインエントリポイント"""
    parser = argparse.ArgumentParser(description="カメラ映像テスト")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="再生時間（秒）。デフォルト: 10.0",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="カメラデバイス番号。デフォルト: 0",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_WIDTH,
        help=f"映像幅。デフォルト: {DEFAULT_WIDTH}",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help=f"映像高さ。デフォルト: {DEFAULT_HEIGHT}",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=f"フレームレート。デフォルト: {DEFAULT_FPS}",
    )
    parser.add_argument(
        "--video-codec-type",
        type=str,
        default=None,
        choices=["AV1", "H264", "H265", "VP8", "VP9"],
        help="ビデオコーデック。指定しない場合は生データ（I420）を直接表示",
    )
    parser.add_argument(
        "--video-bitrate",
        type=int,
        default=8000,
        help="ビットレート (kbps)。デフォルト: 8000",
    )
    parser.add_argument(
        "--flip-horizontal",
        action="store_true",
        help="映像を左右反転（ミラー）",
    )
    parser.add_argument(
        "--flip-vertical",
        action="store_true",
        help="映像を上下反転",
    )
    args = parser.parse_args()

    # コーデック使用の有無
    use_codec = args.video_codec_type is not None

    # コーデック設定
    codec_string = None
    bitrate = 0
    if use_codec:
        codec_map = {
            "AV1": "av01.0.08M.08",
            "H264": "avc1.42001f",
            "H265": "hvc1.1.6.L93.B0",
            "VP8": "vp8",
            "VP9": "vp09.00.10.08",
        }
        codec_string = codec_map[args.video_codec_type]
        bitrate = args.video_bitrate * 1000  # kbps -> bps

    width = args.width
    height = args.height
    fps = args.fps
    total_frames = int(args.duration * fps)
    frame_interval = 1.0 / fps

    if use_codec:
        print("カメラ映像テスト (with webcodecs-py)")
    else:
        print("カメラ映像テスト (生データ)")
    print(f"SDL Version: {get_version()}")
    print(f"GPU Driver: {get_gpu_driver()}")
    print(f"Resolution: {width}x{height}")
    print(f"FPS: {fps}")
    if use_codec:
        print(f"Codec: {args.video_codec_type} ({codec_string})")
        print(f"Bitrate: {args.video_bitrate} kbps")
    else:
        print("Codec: None (生データ I420)")
    print(f"Duration: {args.duration}s ({total_frames} frames)")
    print()

    # カメラを開く
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"エラー: カメラ {args.camera} を開けませんでした")
        return

    # カメラの解像度を設定
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    # 実際の解像度を取得
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"カメラ実際の解像度: {actual_width}x{actual_height}")
    print(f"カメラ実際の FPS: {actual_fps}")

    # 実際の解像度を使用
    width = actual_width
    height = actual_height
    print()

    # エンコード済みチャンクとデコード済みフレームのキュー
    encoded_chunks: deque[EncodedVideoChunk] = deque()
    decoded_frames: deque[VideoFrame] = deque()

    # H264/H265 用: デコーダ設定済みフラグ
    decoder_configured = False
    encoder = None
    decoder = None

    if use_codec:
        assert codec_string is not None

        # デコーダのコールバック
        def on_decode_output(frame: VideoFrame):
            decoded_frames.append(frame)

        def on_decode_error(error: str):
            print(f"Decode error: {error}")

        # デコーダを初期化
        decoder = VideoDecoder(on_decode_output, on_decode_error)

        # エンコーダのコールバック
        def on_encode_output(chunk: EncodedVideoChunk, metadata=None):
            nonlocal decoder_configured
            # H264/H265: 最初のキーフレームで description を取得しデコーダを再設定
            if (
                not decoder_configured
                and args.video_codec_type in ["H264", "H265"]
                and metadata is not None
            ):
                decoder_config_meta = metadata.get("decoderConfig")
                if decoder_config_meta is not None:
                    description = decoder_config_meta.get("description")
                    if description is not None:
                        decoder.configure(
                            {
                                "codec": codec_string,
                                "coded_width": width,
                                "coded_height": height,
                                "description": bytes(description),
                            }
                        )
                        decoder_configured = True
            encoded_chunks.append(chunk)

        def on_encode_error(error: str):
            print(f"Encode error: {error}")

        # エンコーダを初期化
        encoder = VideoEncoder(on_encode_output, on_encode_error)
        encoder_config: VideoEncoderConfig = {
            "codec": codec_string,
            "width": width,
            "height": height,
            "bitrate": bitrate,
            "framerate": float(fps),
            "latency_mode": LatencyMode.REALTIME,
            "hardware_acceleration_engine": (
                HardwareAccelerationEngine.APPLE_VIDEO_TOOLBOX
                if args.video_codec_type in ["H264", "H265"]
                else None
            ),
        }
        encoder.configure(encoder_config)

        # AV1/VP8/VP9 は即座に設定、H264/H265 は最初のキーフレーム時に再設定
        if args.video_codec_type in ["AV1", "VP8", "VP9"]:
            decoder.configure({"codec": codec_string})
            decoder_configured = True

    # raw-player を初期化 (enqueue API)
    player = VideoPlayer(
        width=width,
        height=height,
        title=f"Camera Test ({width}x{height} @ {fps}fps)",
    )

    # キーコールバックを設定（ESC または q で終了）
    def on_key(key: int) -> bool:
        # ESC (27) または q (113) で終了
        if key == 27 or key == 113:
            return False
        return True

    player.set_key_callback(on_key)
    player.play()

    print(f"GPU Renderer: {player.renderer_name}")
    if use_codec:
        print(f"Encoder: {args.video_codec_type} ({codec_string})")
    print("ESC または q キーで終了...")
    print()

    frame_number = 0
    rendered_frames = 0
    start_time = time.perf_counter()

    # 統計用
    capture_times: list[float] = []
    overlay_times: list[float] = []
    encode_times: list[float] = []
    decode_times: list[float] = []
    enqueue_times: list[float] = []

    # フレームサイズ統計用
    raw_frame_sizes: list[int] = []  # 生データ (I420)
    encoded_frame_sizes: list[int] = []  # エンコード後
    decoded_frame_sizes: list[int] = []  # デコード後

    try:
        while player.is_open and frame_number < total_frames:
            # SDL イベントを処理（フレームレンダリングも行う）
            if not player.poll_events():
                break

            # カメラからフレームを取得
            capture_start = time.perf_counter()
            ret, bgr_frame = cap.read()
            if not ret:
                print("カメラからフレームを取得できませんでした")
                break
            capture_time = time.perf_counter() - capture_start
            capture_times.append(capture_time)

            # 反転処理
            if args.flip_horizontal and args.flip_vertical:
                bgr_frame = cv2.flip(bgr_frame, -1)
            elif args.flip_horizontal:
                bgr_frame = cv2.flip(bgr_frame, 1)
            elif args.flip_vertical:
                bgr_frame = cv2.flip(bgr_frame, 0)

            # 現在の FPS を計算
            total_elapsed = time.perf_counter() - start_time
            current_fps = frame_number / total_elapsed if total_elapsed > 0 else 0

            # OpenCV でオーバーレイを描画
            overlay_start = time.perf_counter()
            bgr_frame = draw_overlay(
                bgr_frame,
                frame_number,
                width,
                height,
                fps,
                current_fps,
                args.video_codec_type,
            )
            overlay_time = time.perf_counter() - overlay_start
            overlay_times.append(overlay_time)

            # BGR → I420 変換（プレーン分離）
            y_raw, u_raw, v_raw = bgr_to_i420_planes(bgr_frame)
            raw_frame_sizes.append(y_raw.nbytes + u_raw.nbytes + v_raw.nbytes)

            timestamp_us = int(frame_number * 1_000_000 / fps)

            if use_codec:
                # VideoFrame を作成（エンコード用、1 次元 I420）
                i420_data = np.concatenate(
                    [y_raw.flatten(), u_raw.flatten(), v_raw.flatten()]
                )
                video_frame = VideoFrame(
                    i420_data,
                    {
                        "format": VideoPixelFormat.I420,
                        "coded_width": width,
                        "coded_height": height,
                        "timestamp": timestamp_us,
                    },
                )

                # エンコード
                encode_start = time.perf_counter()
                is_key_frame = frame_number % (fps * 2) == 0  # 2秒ごとにキーフレーム
                assert encoder is not None
                encoder.encode(video_frame, {"key_frame": is_key_frame})
                video_frame.close()
                encode_time = time.perf_counter() - encode_start
                encode_times.append(encode_time)

                # エンコードされたチャンクをデコード
                decode_start = time.perf_counter()
                assert decoder is not None
                while encoded_chunks:
                    chunk = encoded_chunks.popleft()
                    encoded_frame_sizes.append(chunk.byte_length)
                    # デコーダが設定されている場合のみデコード
                    if decoder_configured:
                        decoder.decode(chunk)
                decode_time = time.perf_counter() - decode_start
                decode_times.append(decode_time)

                # デコードされたフレームを enqueue
                enqueue_start = time.perf_counter()
                while decoded_frames:
                    decoded_frame = decoded_frames.popleft()
                    # デコーダは I420 (Y, U, V) で出力
                    y_plane, u_plane, v_plane = decoded_frame.planes()
                    decoded_frame_sizes.append(
                        y_plane.nbytes + u_plane.nbytes + v_plane.nbytes
                    )
                    pts_us = decoded_frame.timestamp
                    player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us)
                    decoded_frame.close()
                    rendered_frames += 1
                enqueue_time = time.perf_counter() - enqueue_start
                enqueue_times.append(enqueue_time)
            else:
                # 生データモード: 直接 enqueue
                enqueue_start = time.perf_counter()
                player.enqueue_video_i420(y_raw, u_raw, v_raw, timestamp_us)
                rendered_frames += 1
                enqueue_time = time.perf_counter() - enqueue_start
                enqueue_times.append(enqueue_time)

            frame_number += 1

            # 30 フレームごとに統計を表示
            if frame_number % 30 == 0:
                avg_capture = sum(capture_times[-30:]) / min(30, len(capture_times))
                avg_overlay = sum(overlay_times[-30:]) / min(30, len(overlay_times))
                avg_enqueue = sum(enqueue_times[-30:]) / min(30, len(enqueue_times))
                total_elapsed = time.perf_counter() - start_time
                actual_fps = frame_number / total_elapsed
                if use_codec:
                    avg_encode = sum(encode_times[-30:]) / min(30, len(encode_times))
                    avg_decode = sum(decode_times[-30:]) / min(30, len(decode_times))
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"capture={avg_capture * 1000:.1f}ms, "
                        f"overlay={avg_overlay * 1000:.1f}ms, "
                        f"encode={avg_encode * 1_000_000:.0f}us, "
                        f"decode={avg_decode * 1_000_000:.0f}us, "
                        f"enqueue={avg_enqueue * 1000:.1f}ms"
                    )
                else:
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"capture={avg_capture * 1000:.1f}ms, "
                        f"overlay={avg_overlay * 1000:.1f}ms, "
                        f"enqueue={avg_enqueue * 1000:.1f}ms"
                    )

            # FPS タイミング調整（絶対時間ベース）
            next_frame_time = start_time + (frame_number) * frame_interval
            wait_time = next_frame_time - time.perf_counter()
            if wait_time > 0:
                time.sleep(wait_time)

    except KeyboardInterrupt:
        print("\n中断されました")

    # カメラを解放
    cap.release()

    # エンコーダ/デコーダをフラッシュしてクリーンアップ
    if use_codec:
        assert encoder is not None
        assert decoder is not None
        encoder.flush()
        while encoded_chunks:
            chunk = encoded_chunks.popleft()
            if decoder_configured:
                decoder.decode(chunk)

        if decoder_configured:
            decoder.flush()
        while decoded_frames:
            decoded_frame = decoded_frames.popleft()
            y_plane, u_plane, v_plane = decoded_frame.planes()
            pts_us = decoded_frame.timestamp
            player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us)
            decoded_frame.close()
            rendered_frames += 1

        encoder.close()
        decoder.close()

    # 統計を表示
    total_time = time.perf_counter() - start_time
    if total_time > 0 and frame_number > 0:
        actual_fps = frame_number / total_time
        print()
        print(f"取得フレーム数: {frame_number}")
        print(f"レンダリングフレーム数: {rendered_frames}")
        print(f"平均 FPS: {actual_fps:.2f}")
        if capture_times:
            print(
                f"平均キャプチャ時間: {sum(capture_times) / len(capture_times) * 1000:.2f}ms"
            )
        if overlay_times:
            print(
                f"平均オーバーレイ時間: {sum(overlay_times) / len(overlay_times) * 1000:.2f}ms"
            )
        if encode_times:
            print(
                f"平均エンコード時間: {sum(encode_times) / len(encode_times) * 1_000_000:.0f}us"
            )
        if decode_times:
            print(
                f"平均デコード時間: {sum(decode_times) / len(decode_times) * 1_000_000:.0f}us"
            )
        if enqueue_times:
            print(
                f"平均 enqueue 時間: {sum(enqueue_times) / len(enqueue_times) * 1000:.2f}ms"
            )
        # フレームサイズ統計
        print()
        if raw_frame_sizes:
            avg_raw = sum(raw_frame_sizes) / len(raw_frame_sizes)
            print(f"平均生データサイズ (I420): {avg_raw / 1024:.2f} KB")
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
            print(
                f"圧縮率: {compression_ratio:.1f}x ({avg_encoded / avg_raw * 100:.1f}%)"
            )

        # プレイヤー統計を表示
        print()
        print("Player stats:")
        stats = player.stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

    player.close()
    print("完了")


if __name__ == "__main__":
    main()
