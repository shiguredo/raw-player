"""カメラ映像テスト

uvc-py でカメラ映像を取得し、
webcodecs-py でエンコード/デコードして、
raw-player で表示します。
"""

import argparse
import time
from collections import deque

import numpy as np
import uvc
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


def main():
    """メインエントリポイント"""
    parser = argparse.ArgumentParser(description="カメラ映像テスト")
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="再生時間(秒)。デフォルト: 10.0",
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
        help="ビデオコーデック。指定しない場合は生データ(NV12)を直接表示",
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
        help="映像を左右反転(ミラー)",
    )
    parser.add_argument(
        "--flip-vertical",
        action="store_true",
        help="映像を上下反転",
    )
    parser.add_argument(
        "--native-buffer",
        action="store_true",
        help="ネイティブバッファを使用 (macOS のみ)",
    )
    args = parser.parse_args()

    # コーデック使用の有無
    use_codec = args.video_codec_type is not None

    # native_buffer と flip は併用不可
    if args.native_buffer and (args.flip_horizontal or args.flip_vertical):
        print("エラー: --native-buffer と --flip-* オプションは併用できません")
        return

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
        print("Codec: None (生データ NV12)")
    if args.native_buffer:
        print("Native Buffer: 有効")
    print(f"Duration: {args.duration}s ({total_frames} frames)")
    print()

    # デバイス一覧を表示
    devices = uvc.list_devices()
    print(f"利用可能なデバイス: {len(devices)}")
    for device in devices:
        print(f"  [{device.index}] {device.name}")
    print()

    # カメラを開く
    try:
        device = uvc.open(args.camera)
    except RuntimeError as e:
        print(f"エラー: カメラ {args.camera} を開けませんでした: {e}")
        return

    # キャプチャ開始
    device.start(width, height, fps, capture_format=uvc.Format.NV12)

    # 実際の解像度を取得
    print(f"カメラ解像度: {width}x{height}")
    print(f"カメラ FPS: {fps}")
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

    # キーコールバックを設定(ESC または q で終了)
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
    encode_times: list[float] = []
    decode_times: list[float] = []
    enqueue_times: list[float] = []

    # フレームサイズ統計用
    raw_frame_sizes: list[int] = []  # 生データ (NV12)
    encoded_frame_sizes: list[int] = []  # エンコード後
    decoded_frame_sizes: list[int] = []  # デコード後

    try:
        while player.is_open and frame_number < total_frames:
            # SDL イベントを処理(フレームレンダリングも行う)
            if not player.poll_events():
                break

            # カメラからフレームを取得
            capture_start = time.perf_counter()
            uvc_frame = device.get_frame()
            if uvc_frame is None:
                continue
            capture_time = time.perf_counter() - capture_start
            capture_times.append(capture_time)

            timestamp_us = uvc_frame.timestamp

            # native_buffer モード
            if args.native_buffer:
                native_buf = uvc_frame.native_buffer()
                if native_buf is None:
                    print("警告: native_buffer が None です (macOS 以外では使用不可)")
                    continue

                if use_codec:
                    # VideoFrame を作成(エンコード用、native_buffer)
                    video_frame = VideoFrame(
                        native_buf,
                        {
                            "format": VideoPixelFormat.NV12,
                            "coded_width": width,
                            "coded_height": height,
                            "timestamp": timestamp_us,
                        },
                    )

                    # エンコード
                    encode_start = time.perf_counter()
                    is_key_frame = frame_number % (fps * 2) == 0
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
                        if decoder_configured:
                            decoder.decode(chunk)
                    decode_time = time.perf_counter() - decode_start
                    decode_times.append(decode_time)

                    # デコードされたフレームを enqueue
                    enqueue_start = time.perf_counter()
                    while decoded_frames:
                        decoded_frame = decoded_frames.popleft()
                        if decoded_frame.format == VideoPixelFormat.NV12:
                            y_data = decoded_frame.plane(0)
                            uv_data = decoded_frame.plane(1)
                            decoded_frame_sizes.append(y_data.nbytes + uv_data.nbytes)
                            pts_us = decoded_frame.timestamp
                            player.enqueue_video_nv12(y_data, uv_data, pts_us)
                        else:
                            y_data, u_data, v_data = decoded_frame.planes()
                            decoded_frame_sizes.append(
                                y_data.nbytes + u_data.nbytes + v_data.nbytes
                            )
                            pts_us = decoded_frame.timestamp
                            player.enqueue_video_i420(y_data, u_data, v_data, pts_us)
                        decoded_frame.close()
                        rendered_frames += 1
                    enqueue_time = time.perf_counter() - enqueue_start
                    enqueue_times.append(enqueue_time)
                else:
                    # 生データモード: native_buffer を直接 enqueue
                    enqueue_start = time.perf_counter()
                    player.enqueue_video_nv12(native_buf, timestamp_us)
                    rendered_frames += 1
                    enqueue_time = time.perf_counter() - enqueue_start
                    enqueue_times.append(enqueue_time)
            else:
                # numpy 配列モード
                y_plane, uv_plane = uvc_frame.to_nv12()

                # 反転処理
                if args.flip_horizontal and args.flip_vertical:
                    y_plane = np.flip(y_plane, axis=(0, 1)).copy()
                    uv_plane = np.flip(uv_plane, axis=(0, 1)).copy()
                elif args.flip_horizontal:
                    y_plane = np.flip(y_plane, axis=1).copy()
                    uv_plane = np.flip(uv_plane, axis=1).copy()
                elif args.flip_vertical:
                    y_plane = np.flip(y_plane, axis=0).copy()
                    uv_plane = np.flip(uv_plane, axis=0).copy()

                raw_frame_sizes.append(y_plane.nbytes + uv_plane.nbytes)

                if use_codec:
                    # VideoFrame を作成(エンコード用、NV12)
                    video_frame = VideoFrame(
                        y_plane,
                        uv_plane,
                        {
                            "format": VideoPixelFormat.NV12,
                            "coded_width": width,
                            "coded_height": height,
                            "timestamp": timestamp_us,
                        },
                    )

                    # エンコード
                    encode_start = time.perf_counter()
                    is_key_frame = frame_number % (fps * 2) == 0
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
                        if decoder_configured:
                            decoder.decode(chunk)
                    decode_time = time.perf_counter() - decode_start
                    decode_times.append(decode_time)

                    # デコードされたフレームを enqueue
                    enqueue_start = time.perf_counter()
                    while decoded_frames:
                        decoded_frame = decoded_frames.popleft()
                        if decoded_frame.format == VideoPixelFormat.NV12:
                            y_data = decoded_frame.plane(0)
                            uv_data = decoded_frame.plane(1)
                            decoded_frame_sizes.append(y_data.nbytes + uv_data.nbytes)
                            pts_us = decoded_frame.timestamp
                            player.enqueue_video_nv12(y_data, uv_data, pts_us)
                        else:
                            y_data, u_data, v_data = decoded_frame.planes()
                            decoded_frame_sizes.append(
                                y_data.nbytes + u_data.nbytes + v_data.nbytes
                            )
                            pts_us = decoded_frame.timestamp
                            player.enqueue_video_i420(y_data, u_data, v_data, pts_us)
                        decoded_frame.close()
                        rendered_frames += 1
                    enqueue_time = time.perf_counter() - enqueue_start
                    enqueue_times.append(enqueue_time)
                else:
                    # 生データモード: 直接 enqueue
                    enqueue_start = time.perf_counter()
                    player.enqueue_video_nv12(y_plane, uv_plane, timestamp_us)
                    rendered_frames += 1
                    enqueue_time = time.perf_counter() - enqueue_start
                    enqueue_times.append(enqueue_time)

            frame_number += 1

            # 30 フレームごとに統計を表示
            if frame_number % 30 == 0:
                avg_capture = sum(capture_times[-30:]) / min(30, len(capture_times))
                avg_enqueue = sum(enqueue_times[-30:]) / min(30, len(enqueue_times))
                total_elapsed = time.perf_counter() - start_time
                actual_fps = frame_number / total_elapsed
                if use_codec:
                    avg_encode = sum(encode_times[-30:]) / min(30, len(encode_times))
                    avg_decode = sum(decode_times[-30:]) / min(30, len(decode_times))
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"capture={avg_capture * 1_000_000:.0f}us, "
                        f"encode={avg_encode * 1_000_000:.0f}us, "
                        f"decode={avg_decode * 1_000_000:.0f}us, "
                        f"enqueue={avg_enqueue * 1_000_000:.0f}us"
                    )
                else:
                    print(
                        f"Frame {frame_number}/{total_frames}: "
                        f"FPS={actual_fps:.1f}, "
                        f"capture={avg_capture * 1_000_000:.0f}us, "
                        f"enqueue={avg_enqueue * 1_000_000:.0f}us"
                    )

            # FPS タイミング調整(絶対時間ベース)
            next_frame_time = start_time + (frame_number) * frame_interval
            wait_time = next_frame_time - time.perf_counter()
            if wait_time > 0:
                time.sleep(wait_time)

    except KeyboardInterrupt:
        print("\n中断されました")

    # カメラを停止
    device.stop()

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
            if decoded_frame.format == VideoPixelFormat.NV12:
                y_data = decoded_frame.plane(0)
                uv_data = decoded_frame.plane(1)
                pts_us = decoded_frame.timestamp
                player.enqueue_video_nv12(y_data, uv_data, pts_us)
            else:
                y_data, u_data, v_data = decoded_frame.planes()
                pts_us = decoded_frame.timestamp
                player.enqueue_video_i420(y_data, u_data, v_data, pts_us)
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
                f"平均キャプチャ時間: {sum(capture_times) / len(capture_times) * 1_000_000:.0f}us"
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
                f"平均 enqueue 時間: {sum(enqueue_times) / len(enqueue_times) * 1_000_000:.0f}us"
            )
        # フレームサイズ統計
        print()
        if raw_frame_sizes:
            avg_raw = sum(raw_frame_sizes) / len(raw_frame_sizes)
            print(f"平均生データサイズ (NV12): {avg_raw / 1024:.2f} KB")
        if encoded_frame_sizes:
            avg_encoded = sum(encoded_frame_sizes) / len(encoded_frame_sizes)
            print(
                f"平均エンコード後サイズ ({args.video_codec_type}): {avg_encoded / 1024:.2f} KB"
            )
        if decoded_frame_sizes:
            avg_decoded = sum(decoded_frame_sizes) / len(decoded_frame_sizes)
            print(f"平均デコード後サイズ (NV12/I420): {avg_decoded / 1024:.2f} KB")
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
