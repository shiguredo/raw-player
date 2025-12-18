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
