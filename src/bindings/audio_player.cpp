#include "audio_player.h"

#include <algorithm>
#include <cstring>
#include <stdexcept>

AudioPlayer::AudioPlayer() {}

AudioPlayer::~AudioPlayer() {
  stop();
  if (audio_stream_) {
    SDL_DestroyAudioStream(audio_stream_);
    audio_stream_ = nullptr;
  }
}

void AudioPlayer::enqueue_audio(nb::ndarray<nb::c_contig, nb::device::cpu> pcm,
                                int64_t pts_us,
                                int sample_rate) {
  if (sample_rate <= 0) {
    throw std::invalid_argument("sample_rate must be positive");
  }

  std::lock_guard<std::mutex> lock(mutex_);

  // ndarray の検証
  size_t ndim = pcm.ndim();
  if (ndim < 1 || ndim > 2) {
    throw std::runtime_error("Audio data must be 1D or 2D array");
  }

  // チャンネル数を決定
  int channels = 1;
  int frames = static_cast<int>(pcm.shape(0));
  if (ndim == 2) {
    channels = static_cast<int>(pcm.shape(1));
  }

  if (channels <= 0) {
    throw std::invalid_argument("channels must be positive");
  }

  // フォーマットを決定(int16 または float32)
  bool is_float = false;
  int sample_size = 0;
  auto dtype = pcm.dtype();

  if (dtype == nb::dtype<int16_t>()) {
    is_float = false;
    sample_size = 2;
  } else if (dtype == nb::dtype<float>()) {
    is_float = true;
    sample_size = 4;
  } else {
    throw std::runtime_error("Audio data must be int16 or float32");
  }

  // 音声チャンクを作成
  AudioChunk chunk;
  chunk.pts_us = pts_us;
  chunk.sample_rate = sample_rate;
  chunk.channels = channels;
  chunk.is_float = is_float;

  // データをコピー
  size_t data_size = frames * channels * sample_size;
  chunk.data.resize(data_size);
  std::memcpy(chunk.data.data(), pcm.data(), data_size);

  // enqueue されたサンプル数を記録
  total_samples_enqueued_ += frames;

  audio_queue_.push_back(std::move(chunk));

  // 再生中ならキューを処理
  if (playing_) {
    process_audio_queue();
  }
}

void AudioPlayer::process_audio_queue() {
  // キュー内の全音声チャンクを処理
  while (!audio_queue_.empty()) {
    auto& chunk = audio_queue_.front();

    // 音声ストリームの作成または再設定が必要かチェック
    // audio_started_ が false の場合も再初期化が必要 (stop 後の再開)
    bool need_new_stream = (audio_stream_ == nullptr) || !audio_started_ ||
                           (chunk.sample_rate != audio_sample_rate_) ||
                           (chunk.channels != audio_channels_) ||
                           (chunk.is_float != audio_is_float_);

    if (need_new_stream) {
      // 古いストリームを破棄
      if (audio_stream_) {
        SDL_DestroyAudioStream(audio_stream_);
        audio_stream_ = nullptr;
      }

      // 新しいストリームを作成
      SDL_AudioSpec spec = {};
      spec.freq = chunk.sample_rate;
      spec.channels = chunk.channels;
      spec.format = chunk.is_float ? SDL_AUDIO_F32 : SDL_AUDIO_S16;

      audio_stream_ = SDL_OpenAudioDeviceStream(
          SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);

      if (!audio_stream_) {
        throw std::runtime_error(
            std::string("Failed to create audio stream: ") + SDL_GetError());
      }

      // 音量を適用
      SDL_SetAudioStreamGain(audio_stream_, volume_);

      // 再生を再開
      if (!SDL_ResumeAudioStreamDevice(audio_stream_)) {
        throw std::runtime_error(
            std::string("Failed to resume audio device: ") + SDL_GetError());
      }

      // 状態を更新
      audio_sample_rate_ = chunk.sample_rate;
      audio_channels_ = chunk.channels;
      audio_is_float_ = chunk.is_float;
      audio_samples_written_ = 0;
      first_audio_pts_us_ = chunk.pts_us;
      audio_started_ = true;
    }

    // ストリームにデータを送信
    if (!SDL_PutAudioStreamData(audio_stream_, chunk.data.data(),
                                static_cast<int>(chunk.data.size()))) {
      throw std::runtime_error(std::string("Failed to queue audio data: ") +
                               SDL_GetError());
    }

    // 書き込んだサンプル数を更新
    int sample_size = chunk.is_float ? 4 : 2;
    int frames =
        static_cast<int>(chunk.data.size()) / (chunk.channels * sample_size);
    audio_samples_written_ += frames;
    chunks_played_++;

    audio_queue_.pop_front();
  }
}

int64_t AudioPlayer::get_audio_clock_us() const {
  if (!audio_stream_ || !audio_started_) {
    return 0;
  }

  // SDL 内のキュー済みバイト数を取得
  int queued_bytes = SDL_GetAudioStreamQueued(audio_stream_);
  if (queued_bytes < 0) {
    queued_bytes = 0;
  }
  int sample_size = audio_is_float_ ? 4 : 2;
  int bytes_per_frame = audio_channels_ * sample_size;
  int queued_frames =
      (bytes_per_frame > 0) ? (queued_bytes / bytes_per_frame) : 0;

  // 再生済みサンプル数を計算
  int64_t played_samples = audio_samples_written_ - queued_frames;
  if (played_samples < 0)
    played_samples = 0;

  // マイクロ秒に変換
  int64_t played_us = (played_samples * 1000000) / audio_sample_rate_;
  return first_audio_pts_us_ + played_us;
}

void AudioPlayer::play() {
  std::lock_guard<std::mutex> lock(mutex_);

  // 再生開始時刻を記録(初回のみ)
  if (play_start_time_ns_ == 0) {
    play_start_time_ns_ = SDL_GetTicksNS();
  }

  playing_ = true;

  // キュー内の音声を処理
  process_audio_queue();

  // ストリームが存在すれば再開
  if (audio_stream_) {
    if (!SDL_ResumeAudioStreamDevice(audio_stream_)) {
      playing_ = false;
      throw std::runtime_error(std::string("Failed to resume audio device: ") +
                               SDL_GetError());
    }
  }
}

void AudioPlayer::pause() {
  std::lock_guard<std::mutex> lock(mutex_);

  playing_ = false;

  if (audio_stream_) {
    SDL_PauseAudioStreamDevice(audio_stream_);
  }
}

void AudioPlayer::stop() {
  std::lock_guard<std::mutex> lock(mutex_);

  playing_ = false;

  if (audio_stream_) {
    SDL_PauseAudioStreamDevice(audio_stream_);
    SDL_ClearAudioStream(audio_stream_);
  }

  // キューをクリア
  audio_queue_.clear();
  audio_samples_written_ = 0;
  audio_started_ = false;

  // 拡張統計をリセット
  total_samples_enqueued_ = 0;
  play_start_time_ns_ = 0;
  chunks_played_ = 0;
}

bool AudioPlayer::is_playing() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return playing_;
}

void AudioPlayer::set_volume(float volume) {
  std::lock_guard<std::mutex> lock(mutex_);

  volume_ = std::max(0.0f, std::min(1.0f, volume));

  if (audio_stream_) {
    SDL_SetAudioStreamGain(audio_stream_, volume_);
  }
}

float AudioPlayer::get_volume() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return volume_;
}

nb::dict AudioPlayer::stats() const {
  std::lock_guard<std::mutex> lock(mutex_);

  nb::dict result;

  // キューサイズ
  result["audio_queue_size"] = static_cast<int>(audio_queue_.size());

  // 音声バッファ(ミリ秒)
  float audio_buffer_ms = 0.0f;
  if (audio_stream_ && audio_sample_rate_ > 0) {
    int queued_bytes = SDL_GetAudioStreamQueued(audio_stream_);
    if (queued_bytes < 0) {
      queued_bytes = 0;
    }
    int sample_size = audio_is_float_ ? 4 : 2;
    int bytes_per_frame = audio_channels_ * sample_size;
    if (bytes_per_frame > 0) {
      int queued_frames = queued_bytes / bytes_per_frame;
      audio_buffer_ms =
          (queued_frames * 1000.0f) / static_cast<float>(audio_sample_rate_);
    }
  }
  result["audio_buffer_ms"] = audio_buffer_ms;

  // 再生したチャンク数
  result["chunks_played"] = chunks_played_;

  // 現在の音声クロック
  result["audio_clock_us"] = get_audio_clock_us();

  // 音声フォーマット情報
  result["sample_rate"] = audio_sample_rate_;
  result["channels"] = audio_channels_;
  result["is_float"] = audio_is_float_;

  // 拡張統計情報
  result["total_samples_enqueued"] = total_samples_enqueued_;

  // 再生済みサンプル数を計算
  int64_t total_samples_played = 0;
  if (audio_stream_ && audio_sample_rate_ > 0) {
    int queued_bytes = SDL_GetAudioStreamQueued(audio_stream_);
    if (queued_bytes < 0) {
      queued_bytes = 0;
    }
    int sample_size = audio_is_float_ ? 4 : 2;
    int bytes_per_frame = audio_channels_ * sample_size;
    if (bytes_per_frame > 0) {
      int queued_frames = queued_bytes / bytes_per_frame;
      total_samples_played = audio_samples_written_ - queued_frames;
      if (total_samples_played < 0) {
        total_samples_played = 0;
      }
    }
  }
  result["total_samples_played"] = total_samples_played;

  // 経過時間(ms)
  double elapsed_time_ms = 0.0;
  if (play_start_time_ns_ > 0) {
    uint64_t now_ns = SDL_GetTicksNS();
    elapsed_time_ms =
        static_cast<double>(now_ns - play_start_time_ns_) / 1000000.0;
  }
  result["elapsed_time_ms"] = elapsed_time_ms;

  // ビットレート(kbps)
  double audio_bitrate_kbps = 0.0;
  if (audio_sample_rate_ > 0 && audio_channels_ > 0) {
    int sample_size = audio_is_float_ ? 4 : 2;
    audio_bitrate_kbps = static_cast<double>(audio_sample_rate_) *
                         audio_channels_ * sample_size * 8.0 / 1000.0;
  }
  result["audio_bitrate_kbps"] = audio_bitrate_kbps;

  return result;
}

void init_audio_player(nb::module_& m) {
  nb::class_<AudioPlayer>(m, "AudioPlayer")
      .def(nb::init<>(), nb::sig("def __init__(self) -> None"))
      .def("enqueue_audio", &AudioPlayer::enqueue_audio, nb::arg("pcm"),
           nb::arg("pts_us"), nb::arg("sample_rate"),
           nb::sig("def enqueue_audio(self, pcm: numpy.ndarray, pts_us: int, "
                   "sample_rate: int) -> None"),
           "Enqueue audio samples for playback.\n\n"
           "Args:\n"
           "    pcm: Audio data as int16 or float32 array.\n"
           "         Shape: (frames, channels) or (frames,) for mono.\n"
           "    pts_us: Presentation timestamp in microseconds.\n"
           "    sample_rate: Sample rate in Hz (e.g., 48000).")
      .def("play", &AudioPlayer::play, nb::sig("def play(self) -> None"),
           "Start or resume playback.")
      .def("pause", &AudioPlayer::pause, nb::sig("def pause(self) -> None"),
           "Pause playback.")
      .def("stop", &AudioPlayer::stop, nb::sig("def stop(self) -> None"),
           "Stop playback and clear the queue.")
      .def("stats", &AudioPlayer::stats,
           nb::sig("def stats(self) -> dict[str, typing.Any]"),
           "Get playback statistics.\n\n"
           "Returns:\n"
           "    Dictionary with keys:\n"
           "        - audio_queue_size: Number of chunks in queue\n"
           "        - audio_buffer_ms: Audio buffer length in milliseconds\n"
           "        - chunks_played: Number of chunks played\n"
           "        - audio_clock_us: Current audio clock in microseconds\n"
           "        - sample_rate: Sample rate in Hz\n"
           "        - channels: Number of channels\n"
           "        - is_float: True if float32 format\n"
           "        - total_samples_enqueued: Total samples enqueued\n"
           "        - total_samples_played: Total samples played\n"
           "        - elapsed_time_ms: Elapsed time in milliseconds\n"
           "        - audio_bitrate_kbps: Audio bitrate in kbps")
      .def_prop_ro("is_playing", &AudioPlayer::is_playing,
                   nb::sig("def is_playing(self) -> bool"),
                   "Whether audio is currently playing.")
      .def_prop_rw("volume", &AudioPlayer::get_volume, &AudioPlayer::set_volume,
                   nb::sig("def volume(self) -> float"),
                   nb::sig("def volume(self, value: float) -> None"),
                   "Playback volume (0.0 to 1.0).");
}
