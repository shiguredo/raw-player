"""native_buffer のテスト."""

import ctypes
import platform

import pytest


@pytest.fixture
def video_player():
    """VideoPlayer のフィクスチャ."""
    from raw_player import VideoPlayer

    player = VideoPlayer(width=640, height=480)
    yield player
    player.close()


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS でのみ実行する",
)
def test_enqueue_video_nv12_native_buffer_invalid_type(video_player):
    """native_buffer に無効な型を渡した場合のテスト."""
    # 文字列を渡すとエラー (PyCapsule でないため ValueError)
    with pytest.raises(ValueError):
        video_player.enqueue_video_nv12("invalid", 0)

    # 整数を渡すとエラー
    with pytest.raises(ValueError):
        video_player.enqueue_video_nv12(12345, 0)


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS でのみ実行する",
)
def test_enqueue_video_nv12_native_buffer_wrong_capsule_name(video_player):
    """間違った name の PyCapsule を渡した場合のテスト."""
    # 間違った name の PyCapsule を作成
    pythonapi = ctypes.pythonapi
    pythonapi.PyCapsule_New.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
    ]
    pythonapi.PyCapsule_New.restype = ctypes.py_object

    # 適当なポインタ値と間違った name で PyCapsule を作成
    wrong_name_capsule = pythonapi.PyCapsule_New(
        ctypes.c_void_p(0x12345678),
        b"WrongName",
        None,
    )

    with pytest.raises(ValueError):
        video_player.enqueue_video_nv12(wrong_name_capsule, 0)


@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS でのみ実行する",
)
def test_enqueue_video_nv12_native_buffer_no_name_capsule(video_player):
    """name が None の PyCapsule を渡した場合のテスト."""
    pythonapi = ctypes.pythonapi
    pythonapi.PyCapsule_New.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
    ]
    pythonapi.PyCapsule_New.restype = ctypes.py_object

    # name が None の PyCapsule を作成
    no_name_capsule = pythonapi.PyCapsule_New(
        ctypes.c_void_p(0x12345678),
        None,
        None,
    )

    with pytest.raises(ValueError):
        video_player.enqueue_video_nv12(no_name_capsule, 0)
