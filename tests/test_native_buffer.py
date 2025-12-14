"""native_buffer のテスト."""

import platform

import pytest


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS でのみ実行する",
)
def test_enqueue_video_nv12_native_buffer_invalid_type():
    """native_buffer に無効な型を渡した場合のテスト."""
    from raw_player import VideoPlayer

    player = VideoPlayer(width=640, height=480)

    # 文字列を渡すとエラー (PyCapsule でないため ValueError)
    with pytest.raises(ValueError):
        player.enqueue_video_nv12("invalid", 0)

    # 整数を渡すとエラー
    with pytest.raises(ValueError):
        player.enqueue_video_nv12(12345, 0)

    player.close()
