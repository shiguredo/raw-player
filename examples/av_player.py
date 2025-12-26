"""カメラ映像とマイク音声を同時に再生するサンプル

uvc-py でカメラ映像を取得し、
portaudio-py でマイク音声を取得し、
raw-player で映像表示と音声再生を行う。
"""

import argparse
import signal
import sys
import time

import numpy as np
import portaudio as pa
import uvc

from raw_player import AudioPlayer, VideoPlayer, get_gpu_driver, get_version

IS_MACOS = sys.platform == "darwin"


def parse_args() -> argparse.Namespace:
    """コマンドライン引数をパースする"""
    parser = argparse.ArgumentParser(
        description="カメラ映像とマイク音声を同時に再生するサンプル"
    )
    parser.add_argument(
        "--video-device",
        type=str,
        default=None,
        help="映像デバイスインデックス、unique_id、またはデバイス名",
    )
    parser.add_argument(
        "--audio-device",
        type=int,
        default=None,
        help="音声入力デバイスインデックス",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default="720p",
        help="解像度 (例: 1080p, 720p, 480p, 4k, 1920x1080)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="フレームレート (デフォルト: 30)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48000,
        help="音声サンプルレート (デフォルト: 48000)",
    )
    parser.add_argument(
        "--audio-channels",
        type=int,
        default=1,
        help="音声チャンネル数 (デフォルト: 1)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="再生時間 (秒)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="デバイス一覧を表示して終了",
    )
    if IS_MACOS:
        parser.add_argument(
            "--native-buffer",
            action="store_true",
            default=False,
            help="CVPixelBuffer を直接使用 (macOS のみ)",
        )
    return parser.parse_args()


def parse_resolution(resolution_str: str) -> tuple[int, int]:
    """解像度文字列をパースして (width, height) を返す"""
    resolution_str = resolution_str.lower()

    presets = {
        "4k": (3840, 2160),
        "2160p": (3840, 2160),
        "1440p": (2560, 1440),
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "540p": (960, 540),
        "480p": (640, 480),
        "360p": (640, 360),
        "240p": (320, 240),
    }

    if resolution_str in presets:
        return presets[resolution_str]

    if "x" in resolution_str:
        parts = resolution_str.split("x")
        if len(parts) == 2:
            return (int(parts[0]), int(parts[1]))

    raise ValueError(f"Invalid resolution format: {resolution_str}")


def list_devices() -> None:
    """デバイス一覧を表示する"""
    print("=== 映像デバイス一覧 ===")
    video_devices = uvc.list_devices()
    if not video_devices:
        print("  映像デバイスが見つかりません")
    else:
        for dev in video_devices:
            print(f"  [{dev.index}] {dev.name}")
            print(f"      ID: {dev.unique_id}")

    print()

    print("=== 音声入力デバイス一覧 ===")
    input_devices = list(pa.get_input_devices())
    if not input_devices:
        print("  音声入力デバイスが見つかりません")
    else:
        for idx, dev in input_devices:
            print(
                f"  [{idx}] {dev.name} (Ch: {dev.max_input_channels}, Rate: {dev.default_sample_rate})"
            )


def main() -> None:
    """メインエントリポイント"""
    args = parse_args()

    if args.list_devices:
        list_devices()
        return

    print("=== AV Player ===")
    print(f"SDL Version: {get_version()}")
    print(f"GPU Driver: {get_gpu_driver()}")
    print()

    # 映像デバイスを開く
    video_devices = uvc.list_devices()
    if not video_devices:
        print("映像デバイスが見つかりません")
        return

    print("=== 映像デバイス一覧 ===")
    for dev in video_devices:
        print(f"  [{dev.index}] {dev.name}")

    selected_video_device = None
    if args.video_device is not None:
        try:
            device_index = int(args.video_device, 0)
            if 0 <= device_index < len(video_devices):
                selected_video_device = video_devices[device_index]
        except ValueError:
            pass

        if selected_video_device is None:
            for dev_info in video_devices:
                if dev_info.unique_id == args.video_device:
                    selected_video_device = dev_info
                    break

        if selected_video_device is None:
            for dev_info in video_devices:
                if dev_info.name == args.video_device:
                    selected_video_device = dev_info
                    break

    if selected_video_device is None:
        selected_video_device = video_devices[0]

    print(f"\n映像デバイス: [{selected_video_device.index}] {selected_video_device.name}")

    video_dev = uvc.open(selected_video_device)
    width, height = parse_resolution(args.resolution)
    fps = args.fps

    video_dev.start(width, height, fps, capture_format=uvc.Format.NV12)
    print(f"映像設定: {width}x{height}@{fps}fps")

    # 音声デバイスを開く
    print("\n=== 音声入力デバイス一覧 ===")
    for idx, dev in pa.get_input_devices():
        print(
            f"  [{idx}] {dev.name} (Ch: {dev.max_input_channels}, Rate: {dev.default_sample_rate})"
        )

    audio_device = args.audio_device
    if audio_device is None:
        audio_device = pa.get_default_input_device()

    if audio_device == pa.NO_DEVICE:
        print("音声入力デバイスが見つかりません")
        video_dev.stop()
        return

    audio_device_info = pa.get_device_info(audio_device)
    if audio_device_info is None:
        print("音声デバイス情報の取得に失敗しました")
        video_dev.stop()
        return

    print(f"\n音声デバイス: [{audio_device}] {audio_device_info.name}")

    sample_rate = args.sample_rate
    audio_channels = args.audio_channels
    frames_per_buffer = 512

    input_params = pa.StreamParameters(
        device=audio_device,
        channel_count=audio_channels,
        sample_format=pa.FLOAT32,
        suggested_latency=audio_device_info.default_low_input_latency,
    )
    print(f"音声設定: {sample_rate}Hz, {audio_channels}ch")

    # プレイヤーを作成
    video_player = VideoPlayer(
        width=width,
        height=height,
        title=f"AV Player ({width}x{height}@{fps}fps)",
    )
    audio_player = AudioPlayer()

    def on_key(key: int) -> bool:
        if key == 27 or key == 113:
            return False
        return True

    video_player.set_key_callback(on_key)

    # 終了フラグ
    running = True

    def signal_handler(signum: int, frame: object) -> None:
        nonlocal running
        running = False
        print("\n終了します...")

    signal.signal(signal.SIGINT, signal_handler)

    use_native_buffer = getattr(args, "native_buffer", False)

    print(f"\nGPU Renderer: {video_player.renderer_name}")
    if use_native_buffer:
        print("Native Buffer: 有効")
    print("ESC または q キーで終了")
    print()

    video_player.play()
    audio_player.play()

    start_time = time.time()
    video_frame_count = 0
    audio_pts_us = 0

    def should_continue() -> bool:
        if not running:
            return False
        if not video_player.is_open:
            return False
        if args.duration is not None and (time.time() - start_time) >= args.duration:
            return False
        return True

    with pa.Stream(
        input_parameters=input_params,
        sample_rate=sample_rate,
        frames_per_buffer=frames_per_buffer,
    ) as audio_stream:
        while should_continue():
            if not video_player.poll_events():
                break

            # 映像フレームを取得
            video_frame = video_dev.get_frame()
            if video_frame is not None:
                video_frame_count += 1
                timestamp_us = video_frame.timestamp

                if video_frame.format == uvc.Format.NV12:
                    native_buf = video_frame.native_buffer() if use_native_buffer else None
                    if native_buf is not None:
                        video_player.enqueue_video_nv12(native_buf, timestamp_us)
                    else:
                        y, uv = video_frame.to_nv12()
                        video_player.enqueue_video_nv12(y, uv, timestamp_us)
                elif video_frame.format == uvc.Format.YUY2:
                    native_buf = video_frame.native_buffer() if use_native_buffer else None
                    if native_buf is not None:
                        video_player.enqueue_video_yuy2(native_buf, timestamp_us)
                    else:
                        yuy2 = video_frame.to_yuy2()
                        video_player.enqueue_video_yuy2(yuy2, timestamp_us)

            # 音声データを取得して再生
            audio_data = audio_stream.read_float32(frames_per_buffer)
            audio_player.enqueue_audio(audio_data, audio_pts_us, sample_rate)
            audio_pts_us += int(audio_data.shape[0] * 1_000_000 / sample_rate)

            # 統計表示
            if video_frame_count % 30 == 0 and video_frame_count > 0:
                elapsed = time.time() - start_time
                actual_fps = video_frame_count / elapsed

                video_stats = video_player.stats()
                audio_stats = audio_player.stats()

                print(
                    f"Frame {video_frame_count}: "
                    f"FPS={actual_fps:.1f}, "
                    f"video_queue={video_stats['video_queue_size']}, "
                    f"audio_buffer={audio_stats['audio_buffer_ms']:.1f}ms"
                )

    # 統計を表示 (stop() 前に取得)
    elapsed = time.time() - start_time
    video_stats = video_player.stats()
    audio_stats = audio_player.stats()

    # 停止
    video_dev.stop()
    audio_player.stop()

    print("\n=== 統計 ===")
    print(f"映像フレーム数: {video_frame_count}")
    print(f"時間: {elapsed:.2f}s")
    if elapsed > 0:
        print(f"FPS: {video_frame_count / elapsed:.1f}")

    print("\n映像プレイヤー統計:")
    for key, value in video_stats.items():
        print(f"  {key}: {value}")

    print("\n音声プレイヤー統計:")
    for key, value in audio_stats.items():
        print(f"  {key}: {value}")

    video_player.close()
    print("\n完了")


if __name__ == "__main__":
    main()
