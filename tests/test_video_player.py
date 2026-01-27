import numpy as np
import pytest


def test_set_key_callback():
    """set_key_callback でコールバックを設定できることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    called_keys = []

    def on_key(key: int) -> bool:
        called_keys.append(key)
        return True

    player.set_key_callback(on_key)
    player.close()


def test_set_key_callback_none():
    """set_key_callback に None を渡してコールバックを解除できることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    def on_key(_key: int) -> bool:
        return True

    player.set_key_callback(on_key)
    player.set_key_callback(None)
    player.close()


def test_video_player_stats():
    """VideoPlayer.stats() が期待するキーを返すことを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    stats = player.stats()

    expected_keys = [
        "video_queue_size",
        "audio_queue_ms",
        "dropped_frames",
        "repeated_frames",
        "video_pts_us",
        "audio_pts_us",
        "sync_diff_us",
        "current_video_width",
        "current_video_height",
        "current_fps",
        "total_frames_enqueued",
        "total_frames_rendered",
        "video_buffer_ms",
        "elapsed_time_ms",
        "video_bitrate_kbps",
    ]

    for key in expected_keys:
        assert key in stats, f"stats() に '{key}' が含まれていない"

    player.close()


def test_enqueue_video_i420():
    """enqueue_video_i420 で I420 フレームをエンキューできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)

    stats = player.stats()
    assert stats["video_queue_size"] == 1
    assert stats["total_frames_enqueued"] == 1

    player.close()


def test_enqueue_video_nv12():
    """enqueue_video_nv12 で NV12 フレームをエンキューできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    uv_plane = np.zeros((height // 2, width), dtype=np.uint8)

    player.enqueue_video_nv12(y_plane, uv_plane, pts_us=0)

    stats = player.stats()
    assert stats["video_queue_size"] == 1
    assert stats["total_frames_enqueued"] == 1

    player.close()


def test_enqueue_video_yuy2():
    """enqueue_video_yuy2 で YUY2 フレームをエンキューできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    # YUY2: (H, W, 2) フォーマット
    yuy2_data = np.zeros((height, width, 2), dtype=np.uint8)

    player.enqueue_video_yuy2(yuy2_data, pts_us=0)

    stats = player.stats()
    assert stats["video_queue_size"] == 1
    assert stats["total_frames_enqueued"] == 1

    player.close()


def test_enqueue_video_yuy2_invalid_shape():
    """enqueue_video_yuy2 に不正な shape を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    height = 240
    width = 320

    # 不正な shape: 2D は受け付けない
    invalid_data_2d = np.zeros((height, width * 2), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_yuy2(invalid_data_2d, pts_us=0)

    # 不正な shape: 3番目の次元が 2 でない
    invalid_data_3d = np.zeros((height, width, 3), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_yuy2(invalid_data_3d, pts_us=0)

    player.close()


def test_enqueue_video_rgba():
    """enqueue_video_rgba で RGBA フレームをエンキューできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    # RGBA: (H, W, 4)
    rgba_data = np.zeros((height, width, 4), dtype=np.uint8)

    player.enqueue_video_rgba(rgba_data, pts_us=0)

    stats = player.stats()
    assert stats["video_queue_size"] == 1
    assert stats["total_frames_enqueued"] == 1

    player.close()


def test_enqueue_video_rgba_invalid_shape():
    """enqueue_video_rgba に不正な shape を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    height = 240
    width = 320

    # 不正な shape: (H, W, 3) は RGBA として無効(4 チャンネル必要)
    invalid_data = np.zeros((height, width, 3), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_rgba(invalid_data, pts_us=0)

    player.close()


def test_enqueue_video_bgra():
    """enqueue_video_bgra で BGRA フレームをエンキューできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    # BGRA: (H, W, 4)
    bgra_data = np.zeros((height, width, 4), dtype=np.uint8)

    player.enqueue_video_bgra(bgra_data, pts_us=0)

    stats = player.stats()
    assert stats["video_queue_size"] == 1
    assert stats["total_frames_enqueued"] == 1

    player.close()


def test_enqueue_video_bgra_invalid_shape():
    """enqueue_video_bgra に不正な shape を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    height = 240
    width = 320

    # 不正な shape: (H, W, 3) は BGRA として無効(4 チャンネル必要)
    invalid_data = np.zeros((height, width, 3), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_bgra(invalid_data, pts_us=0)

    player.close()


def test_enqueue_video_i420_invalid_shape():
    """enqueue_video_i420 に不正な shape を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 4, width // 4), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)

    player.close()


def test_video_player_properties():
    """VideoPlayer のプロパティが正しく動作することを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test Title")

    assert player.width == 320
    assert player.height == 240
    assert player.title == "Test Title"
    assert player.is_open is True
    assert player.is_playing is False

    player.title = "New Title"
    assert player.title == "New Title"

    player.close()
    assert player.is_open is False


def test_max_video_queue_size_default():
    """max_video_queue_size のデフォルト値が 5 であることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    assert player.max_video_queue_size == 5

    player.close()


def test_max_video_queue_size_setter():
    """max_video_queue_size を設定できることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    player.max_video_queue_size = 10
    assert player.max_video_queue_size == 10

    player.max_video_queue_size = 3
    assert player.max_video_queue_size == 3

    player.close()


def test_max_video_queue_size_drops_old_frames():
    """キューサイズ上限を超えたときに古いフレームがドロップされることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.max_video_queue_size = 3
    player.play()

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    for i in range(5):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=i * 33333)

    stats = player.stats()
    assert stats["video_queue_size"] == 3
    assert stats["total_frames_enqueued"] == 5
    assert stats["dropped_frames"] == 2

    player.close()


def test_max_video_queue_size_zero_disables_limit():
    """max_video_queue_size が 0 の場合は制限なしになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.max_video_queue_size = 0
    player.play()

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    for i in range(10):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=i * 33333)

    stats = player.stats()
    assert stats["video_queue_size"] == 10
    assert stats["total_frames_enqueued"] == 10
    assert stats["dropped_frames"] == 0

    player.close()


def test_drain_video():
    """drain_video() でキューがクリアされることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")
    player.play()

    height = 240
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    for i in range(5):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=i * 33333)

    stats = player.stats()
    assert stats["video_queue_size"] == 5

    player.drain_video()

    stats = player.stats()
    assert stats["video_queue_size"] == 0

    player.close()


def test_stats_overlay_default_false():
    """stats_overlay のデフォルト値が False であることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    assert player.stats_overlay is False

    player.close()


def test_stats_overlay_toggle():
    """stats_overlay を on/off 切り替えできることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    assert player.stats_overlay is False

    player.stats_overlay = True
    assert player.stats_overlay is True

    player.stats_overlay = False
    assert player.stats_overlay is False

    player.close()


def test_enqueue_audio_zero_sample_rate():
    """enqueue_audio に sample_rate=0 を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    sample_rate = 0
    frames = 1024
    channels = 2

    pcm = np.zeros((frames, channels), dtype=np.int16)

    with pytest.raises(Exception):
        player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    player.close()


def test_enqueue_audio_negative_sample_rate():
    """enqueue_audio に負の sample_rate を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    sample_rate = -48000
    frames = 1024
    channels = 2

    pcm = np.zeros((frames, channels), dtype=np.int16)

    with pytest.raises(Exception):
        player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    player.close()


def test_max_video_queue_size_negative():
    """max_video_queue_size に負値を設定するとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    with pytest.raises(Exception):
        player.max_video_queue_size = -1

    player.close()


def test_enqueue_video_i420_odd_dimensions():
    """enqueue_video_i420 に奇数サイズを渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    # 奇数の高さ
    height = 241
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)

    player.close()


def test_enqueue_video_i420_odd_width():
    """enqueue_video_i420 に奇数の幅を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    # 奇数の幅
    height = 240
    width = 321

    y_plane = np.zeros((height, width), dtype=np.uint8)
    u_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)
    v_plane = np.zeros((height // 2, width // 2), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_i420(y_plane, u_plane, v_plane, pts_us=0)

    player.close()


def test_enqueue_video_nv12_odd_dimensions():
    """enqueue_video_nv12 に奇数サイズを渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    # 奇数の高さ
    height = 241
    width = 320

    y_plane = np.zeros((height, width), dtype=np.uint8)
    uv_plane = np.zeros((height // 2, width), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_nv12(y_plane, uv_plane, pts_us=0)

    player.close()


def test_enqueue_audio_zero_channels():
    """enqueue_audio に channels=0 の配列を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    sample_rate = 48000
    frames = 1024

    # (frames, 0) の形状で channels=0 を作成
    pcm = np.zeros((frames, 0), dtype=np.int16)

    with pytest.raises(Exception):
        player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    player.close()


def test_enqueue_video_yuy2_odd_width():
    """enqueue_video_yuy2 に奇数幅を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.VideoPlayer(320, 240, "Test")

    height = 240
    width = 321

    yuy2_data = np.zeros((height, width, 2), dtype=np.uint8)

    with pytest.raises(Exception):
        player.enqueue_video_yuy2(yuy2_data, pts_us=0)

    player.close()
