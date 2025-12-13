import numpy as np
import pytest


def test_audio_player_stats():
    """AudioPlayer.stats() が期待するキーを返すことを確認"""
    import raw_player

    player = raw_player.AudioPlayer()
    stats = player.stats()

    expected_keys = [
        "audio_queue_size",
        "audio_buffer_ms",
        "chunks_played",
        "audio_clock_us",
        "sample_rate",
        "channels",
        "is_float",
        "total_samples_enqueued",
        "total_samples_played",
        "elapsed_time_ms",
        "audio_bitrate_kbps",
    ]

    for key in expected_keys:
        assert key in stats, f"stats() に '{key}' が含まれていない"


def test_audio_player_enqueue_int16():
    """enqueue_audio で int16 音声データをエンキューできることを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    sample_rate = 48000
    frames = 1024
    channels = 2

    pcm = np.zeros((frames, channels), dtype=np.int16)

    player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    stats = player.stats()
    assert stats["total_samples_enqueued"] == frames


def test_audio_player_enqueue_float32():
    """enqueue_audio で float32 音声データをエンキューできることを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    sample_rate = 48000
    frames = 1024
    channels = 2

    pcm = np.zeros((frames, channels), dtype=np.float32)

    player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    stats = player.stats()
    assert stats["total_samples_enqueued"] == frames


def test_audio_player_enqueue_mono():
    """enqueue_audio でモノラル音声データをエンキューできることを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    sample_rate = 48000
    frames = 1024

    pcm = np.zeros(frames, dtype=np.int16)

    player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)

    stats = player.stats()
    assert stats["total_samples_enqueued"] == frames


def test_audio_player_enqueue_invalid_dtype():
    """enqueue_audio に不正な dtype を渡すとエラーになることを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    sample_rate = 48000
    frames = 1024
    channels = 2

    pcm = np.zeros((frames, channels), dtype=np.float64)

    with pytest.raises(Exception):
        player.enqueue_audio(pcm, pts_us=0, sample_rate=sample_rate)


def test_audio_player_properties():
    """AudioPlayer のプロパティが正しく動作することを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    assert player.is_playing is False
    assert 0.0 <= player.volume <= 1.0

    player.volume = 0.5
    assert player.volume == pytest.approx(0.5)

    player.volume = 0.0
    assert player.volume == pytest.approx(0.0)

    player.volume = 1.0
    assert player.volume == pytest.approx(1.0)


def test_audio_player_volume_clamp():
    """AudioPlayer.volume が 0.0-1.0 の範囲にクランプされることを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    player.volume = -0.5
    assert player.volume == pytest.approx(0.0)

    player.volume = 1.5
    assert player.volume == pytest.approx(1.0)


def test_audio_player_play_pause_stop():
    """AudioPlayer の play/pause/stop が正しく動作することを確認"""
    import raw_player

    player = raw_player.AudioPlayer()

    assert player.is_playing is False

    player.play()
    assert player.is_playing is True

    player.pause()
    assert player.is_playing is False

    player.play()
    assert player.is_playing is True

    player.stop()
    assert player.is_playing is False
