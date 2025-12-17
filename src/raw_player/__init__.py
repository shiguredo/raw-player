"""Raw audio and video playback bindings for Python."""

from .raw_player_ext import (  # ty: ignore[unresolved-import]
    # Classes
    AudioPlayer,
    VideoPlayer,
    get_all_gpu_drivers,
    get_audio_driver,
    get_gpu_driver,
    get_num_gpu_drivers,
    # Functions
    get_version,
    get_video_driver,
)

__all__ = [
    # Classes
    "AudioPlayer",
    "VideoPlayer",
    # Functions
    "get_version",
    "get_audio_driver",
    "get_video_driver",
    "get_gpu_driver",
    "get_num_gpu_drivers",
    "get_all_gpu_drivers",
]
