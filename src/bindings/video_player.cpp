#include "video_player.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <stdexcept>

VideoPlayer::VideoPlayer(int width, int height, const std::string& title)
    : window_width_(width), window_height_(height), title_(title) {
  // ウィンドウを作成
  window_ =
      SDL_CreateWindow(title_.c_str(), window_width_, window_height_,
                       SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY);

  if (!window_) {
    throw std::runtime_error(std::string("Failed to create window: ") +
                             SDL_GetError());
  }

  // GPU アクセラレーションレンダラーを作成
  renderer_ = SDL_CreateRenderer(window_, "gpu");

  // プラットフォーム固有の GPU レンダラーにフォールバック
  if (!renderer_) {
#if defined(__APPLE__)
    renderer_ = SDL_CreateRenderer(window_, "metal");
#elif defined(_WIN32)
    renderer_ = SDL_CreateRenderer(window_, "direct3d12");
    if (!renderer_) {
      renderer_ = SDL_CreateRenderer(window_, "vulkan");
    }
#else
    renderer_ = SDL_CreateRenderer(window_, "vulkan");
#endif
  }

  if (!renderer_) {
    SDL_DestroyWindow(window_);
    window_ = nullptr;
    throw std::runtime_error(std::string("Failed to create GPU renderer: ") +
                             SDL_GetError());
  }

  // VSync を有効化
  SDL_SetRenderVSync(renderer_, 1);

  open_ = true;
}

VideoPlayer::~VideoPlayer() {
  close();
}

void VideoPlayer::create_texture(int width, int height, VideoFormat format) {
  if (texture_) {
    SDL_DestroyTexture(texture_);
    texture_ = nullptr;
  }

  SDL_PixelFormat sdl_format;
  switch (format) {
    case VideoFormat::I420:
      sdl_format = SDL_PIXELFORMAT_IYUV;
      break;
    case VideoFormat::NV12:
      sdl_format = SDL_PIXELFORMAT_NV12;
      break;
    case VideoFormat::YUY2:
      sdl_format = SDL_PIXELFORMAT_YUY2;
      break;
    case VideoFormat::RGBA:
      sdl_format = SDL_PIXELFORMAT_RGBA8888;
      break;
    case VideoFormat::BGRA:
      // BGRA はメモリ上 B, G, R, A の順
      // リトルエンディアンでは SDL_PIXELFORMAT_ARGB8888 が対応
      sdl_format = SDL_PIXELFORMAT_ARGB8888;
      break;
  }

  texture_ = SDL_CreateTexture(renderer_, sdl_format,
                               SDL_TEXTUREACCESS_STREAMING, width, height);

  if (!texture_) {
    throw std::runtime_error(std::string("Failed to create texture: ") +
                             SDL_GetError());
  }

  texture_width_ = width;
  texture_height_ = height;
  texture_format_ = format;

  // スケーリング用の論理プレゼンテーションを更新
  SDL_SetRenderLogicalPresentation(renderer_, width, height,
                                   SDL_LOGICAL_PRESENTATION_LETTERBOX);
}

void VideoPlayer::enqueue_video_i420(
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> y,
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> u,
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> v,
    int64_t pts_us) {
  // 次元を検証
  if (y.ndim() != 2) {
    throw std::invalid_argument("Y plane must be 2D");
  }
  int h = static_cast<int>(y.shape(0));
  int w = static_cast<int>(y.shape(1));

  if (u.ndim() != 2 || u.shape(0) != h / 2 || u.shape(1) != w / 2) {
    throw std::invalid_argument("U plane must be 2D with shape (H/2, W/2)");
  }
  if (v.ndim() != 2 || v.shape(0) != h / 2 || v.shape(1) != w / 2) {
    throw std::invalid_argument("V plane must be 2D with shape (H/2, W/2)");
  }

  VideoFrame frame;
  frame.pts_us = pts_us;
  frame.width = w;
  frame.height = h;
  frame.format = VideoFormat::I420;

  // データをコピー
  frame.y_data.resize(y.nbytes());
  std::memcpy(frame.y_data.data(), y.data(), y.nbytes());

  frame.u_data.resize(u.nbytes());
  std::memcpy(frame.u_data.data(), u.data(), u.nbytes());

  frame.v_data.resize(v.nbytes());
  std::memcpy(frame.v_data.data(), v.data(), v.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  // フレームサイズを記録
  last_frame_size_bytes_ = static_cast<int64_t>(
      frame.y_data.size() + frame.u_data.size() + frame.v_data.size());
  total_frames_enqueued_++;
  video_queue_.push_back(std::move(frame));
}

void VideoPlayer::enqueue_video_nv12(
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> y,
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> uv,
    int64_t pts_us) {
  // 次元を検証
  if (y.ndim() != 2) {
    throw std::invalid_argument("Y plane must be 2D");
  }
  int h = static_cast<int>(y.shape(0));
  int w = static_cast<int>(y.shape(1));

  if (uv.ndim() != 2 || uv.shape(0) != h / 2 || uv.shape(1) != w) {
    throw std::invalid_argument("UV plane must be 2D with shape (H/2, W)");
  }

  VideoFrame frame;
  frame.pts_us = pts_us;
  frame.width = w;
  frame.height = h;
  frame.format = VideoFormat::NV12;

  // データをコピー
  frame.y_data.resize(y.nbytes());
  std::memcpy(frame.y_data.data(), y.data(), y.nbytes());

  frame.u_data.resize(uv.nbytes());
  std::memcpy(frame.u_data.data(), uv.data(), uv.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  // フレームサイズを記録
  last_frame_size_bytes_ =
      static_cast<int64_t>(frame.y_data.size() + frame.u_data.size());
  total_frames_enqueued_++;
  video_queue_.push_back(std::move(frame));
}

void VideoPlayer::enqueue_video_yuy2(
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
    int64_t pts_us) {
  // 次元を検証
  if (data.ndim() != 2) {
    throw std::invalid_argument("YUY2 data must be 2D");
  }
  int h = static_cast<int>(data.shape(0));
  int packed_width = static_cast<int>(data.shape(1));

  // YUY2: 2 ピクセルで 4 バイト、つまり width * 2 バイト/行
  if (packed_width % 2 != 0) {
    throw std::invalid_argument(
        "YUY2 data width must be even (expected W*2 bytes per row)");
  }
  int w = packed_width / 2;

  VideoFrame frame;
  frame.pts_us = pts_us;
  frame.width = w;
  frame.height = h;
  frame.format = VideoFormat::YUY2;

  // パックドデータをコピー
  frame.y_data.resize(data.nbytes());
  std::memcpy(frame.y_data.data(), data.data(), data.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  // フレームサイズを記録
  last_frame_size_bytes_ = static_cast<int64_t>(frame.y_data.size());
  total_frames_enqueued_++;
  video_queue_.push_back(std::move(frame));
}

void VideoPlayer::enqueue_video_rgba(
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
    int64_t pts_us) {
  // 次元を検証: (H, W, 4)
  if (data.ndim() != 3) {
    throw std::invalid_argument("RGBA data must be 3D (H, W, 4)");
  }
  int h = static_cast<int>(data.shape(0));
  int w = static_cast<int>(data.shape(1));
  int channels = static_cast<int>(data.shape(2));

  if (channels != 4) {
    throw std::invalid_argument("RGBA data must have 4 channels");
  }

  VideoFrame frame;
  frame.pts_us = pts_us;
  frame.width = w;
  frame.height = h;
  frame.format = VideoFormat::RGBA;

  // パックドデータをコピー
  frame.y_data.resize(data.nbytes());
  std::memcpy(frame.y_data.data(), data.data(), data.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  // フレームサイズを記録
  last_frame_size_bytes_ = static_cast<int64_t>(frame.y_data.size());
  total_frames_enqueued_++;
  video_queue_.push_back(std::move(frame));
}

void VideoPlayer::enqueue_video_bgra(
    nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
    int64_t pts_us) {
  // 次元を検証: (H, W, 4)
  if (data.ndim() != 3) {
    throw std::invalid_argument("BGRA data must be 3D (H, W, 4)");
  }
  int h = static_cast<int>(data.shape(0));
  int w = static_cast<int>(data.shape(1));
  int channels = static_cast<int>(data.shape(2));

  if (channels != 4) {
    throw std::invalid_argument("BGRA data must have 4 channels");
  }

  VideoFrame frame;
  frame.pts_us = pts_us;
  frame.width = w;
  frame.height = h;
  frame.format = VideoFormat::BGRA;

  // パックドデータをコピー
  frame.y_data.resize(data.nbytes());
  std::memcpy(frame.y_data.data(), data.data(), data.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  // フレームサイズを記録
  last_frame_size_bytes_ = static_cast<int64_t>(frame.y_data.size());
  total_frames_enqueued_++;
  video_queue_.push_back(std::move(frame));
}

void VideoPlayer::enqueue_audio(nb::ndarray<nb::c_contig, nb::device::cpu> pcm,
                                int64_t pts_us,
                                int sample_rate) {
  // dtype をチェック
  bool is_float = false;
  if (pcm.dtype() == nb::dtype<float>()) {
    is_float = true;
  } else if (pcm.dtype() == nb::dtype<int16_t>()) {
    is_float = false;
  } else {
    throw std::invalid_argument("Audio must be int16 or float32");
  }

  // チャンネル数を決定
  int channels = 1;
  if (pcm.ndim() == 2) {
    channels = static_cast<int>(pcm.shape(1));
  } else if (pcm.ndim() != 1) {
    throw std::invalid_argument("Audio must be 1D or 2D");
  }

  AudioChunk chunk;
  chunk.pts_us = pts_us;
  chunk.sample_rate = sample_rate;
  chunk.channels = channels;
  chunk.is_float = is_float;

  // データをコピー
  chunk.data.resize(pcm.nbytes());
  std::memcpy(chunk.data.data(), pcm.data(), pcm.nbytes());

  std::lock_guard<std::mutex> lock(mutex_);
  audio_queue_.push_back(std::move(chunk));
}

void VideoPlayer::process_audio_queue() {
  // 音声キューを処理して SDL に送信
  while (!audio_queue_.empty()) {
    auto& chunk = audio_queue_.front();

    // 必要に応じて音声ストリームを作成または再設定
    if (!audio_stream_ || audio_sample_rate_ != chunk.sample_rate ||
        audio_channels_ != chunk.channels ||
        audio_is_float_ != chunk.is_float) {
      if (audio_stream_) {
        SDL_DestroyAudioStream(audio_stream_);
      }

      SDL_AudioSpec spec;
      spec.format = chunk.is_float ? SDL_AUDIO_F32 : SDL_AUDIO_S16;
      spec.channels = chunk.channels;
      spec.freq = chunk.sample_rate;

      audio_stream_ = SDL_OpenAudioDeviceStream(
          SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, nullptr, nullptr);

      if (!audio_stream_) {
        throw std::runtime_error(
            std::string("Failed to create audio stream: ") + SDL_GetError());
      }

      SDL_SetAudioStreamGain(audio_stream_, volume_);

      if (playing_) {
        SDL_ResumeAudioStreamDevice(audio_stream_);
      }

      audio_sample_rate_ = chunk.sample_rate;
      audio_channels_ = chunk.channels;
      audio_is_float_ = chunk.is_float;

      // 音声タイミングをリセット
      audio_samples_written_ = 0;
      first_audio_pts_us_ = chunk.pts_us;
      audio_started_ = true;
    }

    // SDL に送信
    if (!SDL_PutAudioStreamData(audio_stream_, chunk.data.data(),
                                static_cast<int>(chunk.data.size()))) {
      throw std::runtime_error(std::string("Failed to queue audio: ") +
                               SDL_GetError());
    }

    // 書き込んだサンプル数を更新
    int sample_size = (chunk.is_float ? 4 : 2) * chunk.channels;
    audio_samples_written_ +=
        static_cast<int64_t>(chunk.data.size()) / sample_size;

    audio_queue_.pop_front();
  }
}

int64_t VideoPlayer::get_audio_clock_us() const {
  if (!audio_stream_ || !audio_started_) {
    return 0;
  }

  int queued_bytes = SDL_GetAudioStreamQueued(audio_stream_);
  int sample_size = (audio_is_float_ ? 4 : 2) * audio_channels_;
  int64_t queued_samples = queued_bytes / sample_size;
  int64_t played_samples = audio_samples_written_ - queued_samples;

  if (played_samples < 0) {
    played_samples = 0;
  }

  int64_t played_us = (played_samples * 1000000LL) / audio_sample_rate_;
  return first_audio_pts_us_ + played_us;
}

void VideoPlayer::render_frame_internal(const VideoFrame& frame) {
  // 解像度またはフォーマットが変わったらテクスチャを再作成
  if (frame.width != texture_width_ || frame.height != texture_height_ ||
      frame.format != texture_format_) {
    create_texture(frame.width, frame.height, frame.format);
  }

  if (frame.format == VideoFormat::I420) {
    int y_pitch = frame.width;
    int uv_pitch = frame.width / 2;

    if (!SDL_UpdateYUVTexture(texture_, nullptr, frame.y_data.data(), y_pitch,
                              frame.u_data.data(), uv_pitch,
                              frame.v_data.data(), uv_pitch)) {
      throw std::runtime_error(std::string("Failed to update YUV texture: ") +
                               SDL_GetError());
    }
  } else if (frame.format == VideoFormat::NV12) {
    int y_pitch = frame.width;
    int uv_pitch = frame.width;

    if (!SDL_UpdateNVTexture(texture_, nullptr, frame.y_data.data(), y_pitch,
                             frame.u_data.data(), uv_pitch)) {
      throw std::runtime_error(std::string("Failed to update NV12 texture: ") +
                               SDL_GetError());
    }
  } else if (frame.format == VideoFormat::YUY2) {
    // YUY2: パックドフォーマット、pitch は width * 2
    int pitch = frame.width * 2;

    if (!SDL_UpdateTexture(texture_, nullptr, frame.y_data.data(), pitch)) {
      throw std::runtime_error(std::string("Failed to update YUY2 texture: ") +
                               SDL_GetError());
    }
  } else if (frame.format == VideoFormat::RGBA) {
    // RGBA: パックドフォーマット、pitch は width * 4
    int pitch = frame.width * 4;

    if (!SDL_UpdateTexture(texture_, nullptr, frame.y_data.data(), pitch)) {
      throw std::runtime_error(std::string("Failed to update RGBA texture: ") +
                               SDL_GetError());
    }
  } else {
    // BGRA: パックドフォーマット、pitch は width * 4
    int pitch = frame.width * 4;

    if (!SDL_UpdateTexture(texture_, nullptr, frame.y_data.data(), pitch)) {
      throw std::runtime_error(std::string("Failed to update BGRA texture: ") +
                               SDL_GetError());
    }
  }

  SDL_SetRenderDrawColor(renderer_, 0, 0, 0, 255);
  SDL_RenderClear(renderer_);
  SDL_RenderTexture(renderer_, texture_, nullptr, nullptr);
  SDL_RenderPresent(renderer_);

  last_video_pts_us_ = frame.pts_us;
  total_frames_rendered_++;

  // FPS 計算を更新
  fps_frame_count_++;
  uint64_t now_ns = SDL_GetTicksNS();
  uint64_t elapsed_ns = now_ns - fps_calc_start_ns_;

  // 1 秒経過したら FPS を更新
  if (elapsed_ns >= 1000000000ULL) {
    current_fps_ = static_cast<float>(fps_frame_count_) * 1000000000.0f /
                   static_cast<float>(elapsed_ns);
    fps_calc_start_ns_ = now_ns;
    fps_frame_count_ = 0;
  }
}

void VideoPlayer::render_next_frame() {
  if (!playing_ || !renderer_) {
    return;
  }

  // まず音声キューを処理
  process_audio_queue();

  // 映像キューが空なら何もしない
  if (video_queue_.empty()) {
    return;
  }

  // 現在のクロックを取得
  int64_t clock_us;
  if (audio_started_) {
    // 音声マスター
    clock_us = get_audio_clock_us();
  } else {
    // 映像のみモード: ウォールクロックを基準に使用
    if (!video_only_started_) {
      // 最初のフレーム: ウォールクロックと PTS を記録
      video_start_time_ns_ = SDL_GetTicksNS();
      first_video_pts_us_ = video_queue_.front().pts_us;
      video_only_started_ = true;
    }

    // 経過時間からクロックを計算
    uint64_t elapsed_ns = SDL_GetTicksNS() - video_start_time_ns_;
    int64_t elapsed_us = static_cast<int64_t>(elapsed_ns / 1000);
    clock_us = first_video_pts_us_ + elapsed_us;
  }

  // AV 同期で映像キューを処理
  while (!video_queue_.empty()) {
    auto& frame = video_queue_.front();
    int64_t diff = frame.pts_us - clock_us;

    if (diff < -sync_threshold_us_) {
      // フレームが遅れている → ドロップ
      video_queue_.pop_front();
      dropped_frames_++;
      continue;
    }

    if (diff > sync_threshold_us_) {
      // フレームが早い → 待機
      repeated_frames_++;
      break;
    }

    // フレームが許容範囲内 → レンダリング
    render_frame_internal(frame);
    video_queue_.pop_front();
    break;
  }
}

void VideoPlayer::play() {
  std::lock_guard<std::mutex> lock(mutex_);

  if (audio_stream_) {
    if (!SDL_ResumeAudioStreamDevice(audio_stream_)) {
      throw std::runtime_error(std::string("Failed to resume audio: ") +
                               SDL_GetError());
    }
  }

  // 再生開始時刻を記録(初回のみ)
  if (play_start_time_ns_ == 0) {
    play_start_time_ns_ = SDL_GetTicksNS();
    fps_calc_start_ns_ = play_start_time_ns_;
  }

  playing_ = true;
}

void VideoPlayer::pause() {
  std::lock_guard<std::mutex> lock(mutex_);

  if (audio_stream_) {
    SDL_PauseAudioStreamDevice(audio_stream_);
  }

  playing_ = false;
}

void VideoPlayer::stop() {
  std::lock_guard<std::mutex> lock(mutex_);

  if (audio_stream_) {
    SDL_PauseAudioStreamDevice(audio_stream_);
    SDL_ClearAudioStream(audio_stream_);
  }

  video_queue_.clear();
  audio_queue_.clear();
  audio_samples_written_ = 0;
  first_audio_pts_us_ = 0;
  audio_started_ = false;
  last_video_pts_us_ = 0;
  dropped_frames_ = 0;
  repeated_frames_ = 0;
  playing_ = false;

  // 映像のみモードの状態もリセット
  video_start_time_ns_ = 0;
  first_video_pts_us_ = 0;
  video_only_started_ = false;

  // 拡張統計をリセット
  total_frames_enqueued_ = 0;
  total_frames_rendered_ = 0;
  play_start_time_ns_ = 0;
  last_frame_size_bytes_ = 0;
  fps_calc_start_ns_ = 0;
  fps_frame_count_ = 0;
  current_fps_ = 0.0f;
}

void VideoPlayer::close() {
  std::lock_guard<std::mutex> lock(mutex_);

  // 音声を停止してクリーンアップ
  if (audio_stream_) {
    SDL_PauseAudioStreamDevice(audio_stream_);
    SDL_DestroyAudioStream(audio_stream_);
    audio_stream_ = nullptr;
  }

  // 映像をクリーンアップ
  if (texture_) {
    SDL_DestroyTexture(texture_);
    texture_ = nullptr;
  }
  if (renderer_) {
    SDL_DestroyRenderer(renderer_);
    renderer_ = nullptr;
  }
  if (window_) {
    SDL_DestroyWindow(window_);
    window_ = nullptr;
  }

  // 状態をクリア
  video_queue_.clear();
  audio_queue_.clear();
  playing_ = false;
  open_ = false;

  // 映像のみモードの状態もリセット
  video_start_time_ns_ = 0;
  first_video_pts_us_ = 0;
  video_only_started_ = false;
}

bool VideoPlayer::poll_events() {
  SDL_Event event;
  while (SDL_PollEvent(&event)) {
    if (event.type == SDL_EVENT_QUIT) {
      std::lock_guard<std::mutex> lock(mutex_);
      open_ = false;
      return false;
    }
    if (event.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED) {
      std::lock_guard<std::mutex> lock(mutex_);
      open_ = false;
      return false;
    }
    if (event.type == SDL_EVENT_KEY_DOWN) {
      std::lock_guard<std::mutex> lock(mutex_);
      if (key_callback_) {
        int key_code = static_cast<int>(event.key.key);
        bool should_continue = key_callback_(key_code);
        if (!should_continue) {
          open_ = false;
          return false;
        }
      }
    }
  }

  // 次のフレームをレンダリング
  {
    std::lock_guard<std::mutex> lock(mutex_);
    render_next_frame();
  }

  return true;
}

bool VideoPlayer::is_open() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return open_;
}

bool VideoPlayer::is_playing() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return playing_;
}

int VideoPlayer::width() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return window_width_;
}

int VideoPlayer::height() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return window_height_;
}

std::string VideoPlayer::title() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return title_;
}

void VideoPlayer::set_title(const std::string& title) {
  std::lock_guard<std::mutex> lock(mutex_);
  title_ = title;
  if (window_) {
    SDL_SetWindowTitle(window_, title_.c_str());
  }
}

std::string VideoPlayer::renderer_name() const {
  std::lock_guard<std::mutex> lock(mutex_);
  if (!renderer_) {
    return "";
  }
  const char* name = SDL_GetRendererName(renderer_);
  return name ? std::string(name) : "";
}

void VideoPlayer::set_volume(float volume) {
  std::lock_guard<std::mutex> lock(mutex_);

  volume_ = std::max(0.0f, std::min(1.0f, volume));

  if (audio_stream_) {
    SDL_SetAudioStreamGain(audio_stream_, volume_);
  }
}

float VideoPlayer::get_volume() const {
  std::lock_guard<std::mutex> lock(mutex_);
  return volume_;
}

void VideoPlayer::set_key_callback(std::function<bool(int)> callback) {
  std::lock_guard<std::mutex> lock(mutex_);
  key_callback_ = callback;
}

nb::dict VideoPlayer::stats() const {
  std::lock_guard<std::mutex> lock(mutex_);

  nb::dict result;
  result["video_queue_size"] = static_cast<int>(video_queue_.size());

  // 音声キュー(ミリ秒)
  if (audio_stream_) {
    int queued_bytes = SDL_GetAudioStreamQueued(audio_stream_);
    int sample_size = (audio_is_float_ ? 4 : 2) * audio_channels_;
    int64_t queued_samples = queued_bytes / sample_size;
    double audio_queue_ms = (audio_sample_rate_ > 0)
                                ? (queued_samples * 1000.0 / audio_sample_rate_)
                                : 0.0;
    result["audio_queue_ms"] = audio_queue_ms;
  } else {
    result["audio_queue_ms"] = 0.0;
  }

  result["dropped_frames"] = dropped_frames_;
  result["repeated_frames"] = repeated_frames_;
  result["video_pts_us"] = last_video_pts_us_;
  result["audio_pts_us"] = get_audio_clock_us();
  result["sync_diff_us"] = get_audio_clock_us() - last_video_pts_us_;
  result["current_video_width"] = texture_width_;
  result["current_video_height"] = texture_height_;

  // 拡張統計情報
  result["current_fps"] = current_fps_;
  result["total_frames_enqueued"] = total_frames_enqueued_;
  result["total_frames_rendered"] = total_frames_rendered_;

  // 映像バッファ時間(ms)
  double video_buffer_ms = 0.0;
  if (video_queue_.size() >= 2) {
    int64_t first_pts = video_queue_.front().pts_us;
    int64_t last_pts = video_queue_.back().pts_us;
    video_buffer_ms = static_cast<double>(last_pts - first_pts) / 1000.0;
  }
  result["video_buffer_ms"] = video_buffer_ms;

  // 経過時間(ms)
  double elapsed_time_ms = 0.0;
  if (play_start_time_ns_ > 0) {
    uint64_t now_ns = SDL_GetTicksNS();
    elapsed_time_ms =
        static_cast<double>(now_ns - play_start_time_ns_) / 1000000.0;
  }
  result["elapsed_time_ms"] = elapsed_time_ms;

  // ビットレート(kbps)
  double video_bitrate_kbps = 0.0;
  if (current_fps_ > 0 && last_frame_size_bytes_ > 0) {
    video_bitrate_kbps = static_cast<double>(last_frame_size_bytes_) *
                         current_fps_ * 8.0 / 1000.0;
  }
  result["video_bitrate_kbps"] = video_bitrate_kbps;

  return result;
}

// === Python バインディング ===

void init_video_player(nb::module_& m) {
  nb::class_<VideoPlayer>(m, "VideoPlayer")
      .def(nb::init<int, int, const std::string&>(), nb::arg("width") = 960,
           nb::arg("height") = 540, nb::arg("title") = "Raw Player",
           nb::sig("def __init__(self, width: int = 960, height: int = 540, "
                   "title: str = 'Raw Player') -> None"),
           "Create a video player with the specified window size.\n\n"
           "Args:\n"
           "    width: Window width (default: 960)\n"
           "    height: Window height (default: 540)\n"
           "    title: Window title (default: 'Raw Player')")

      // Enqueue API
      .def("enqueue_video_i420", &VideoPlayer::enqueue_video_i420, nb::arg("y"),
           nb::arg("u"), nb::arg("v"), nb::arg("pts_us"),
           nb::sig("def enqueue_video_i420(self, y: numpy.ndarray, "
                   "u: numpy.ndarray, v: numpy.ndarray, pts_us: int) -> None"),
           "Enqueue an I420 video frame.\n\n"
           "Args:\n"
           "    y: Y plane, uint8 (H, W)\n"
           "    u: U plane, uint8 (H/2, W/2)\n"
           "    v: V plane, uint8 (H/2, W/2)\n"
           "    pts_us: Presentation timestamp in microseconds")

      .def("enqueue_video_nv12", &VideoPlayer::enqueue_video_nv12, nb::arg("y"),
           nb::arg("uv"), nb::arg("pts_us"),
           nb::sig("def enqueue_video_nv12(self, y: numpy.ndarray, "
                   "uv: numpy.ndarray, pts_us: int) -> None"),
           "Enqueue an NV12 video frame.\n\n"
           "Args:\n"
           "    y: Y plane, uint8 (H, W)\n"
           "    uv: UV plane, uint8 (H/2, W)\n"
           "    pts_us: Presentation timestamp in microseconds")

      .def("enqueue_video_yuy2", &VideoPlayer::enqueue_video_yuy2,
           nb::arg("data"), nb::arg("pts_us"),
           nb::sig("def enqueue_video_yuy2(self, data: numpy.ndarray, "
                   "pts_us: int) -> None"),
           "Enqueue a YUY2 video frame.\n\n"
           "Args:\n"
           "    data: Packed YUY2 data, uint8 (H, W*2)\n"
           "    pts_us: Presentation timestamp in microseconds")

      .def("enqueue_video_rgba", &VideoPlayer::enqueue_video_rgba,
           nb::arg("data"), nb::arg("pts_us"),
           nb::sig("def enqueue_video_rgba(self, data: numpy.ndarray, "
                   "pts_us: int) -> None"),
           "Enqueue an RGBA video frame.\n\n"
           "Args:\n"
           "    data: RGBA data, uint8 (H, W, 4)\n"
           "    pts_us: Presentation timestamp in microseconds")

      .def("enqueue_video_bgra", &VideoPlayer::enqueue_video_bgra,
           nb::arg("data"), nb::arg("pts_us"),
           nb::sig("def enqueue_video_bgra(self, data: numpy.ndarray, "
                   "pts_us: int) -> None"),
           "Enqueue a BGRA video frame.\n\n"
           "Args:\n"
           "    data: BGRA data, uint8 (H, W, 4)\n"
           "    pts_us: Presentation timestamp in microseconds")

      .def("enqueue_audio", &VideoPlayer::enqueue_audio, nb::arg("pcm"),
           nb::arg("pts_us"), nb::arg("sample_rate"),
           nb::sig("def enqueue_audio(self, pcm: numpy.ndarray, pts_us: int, "
                   "sample_rate: int) -> None"),
           "Enqueue audio data.\n\n"
           "Args:\n"
           "    pcm: Audio samples, int16 or float32, shape (frames,) or "
           "(frames, channels)\n"
           "    pts_us: Presentation timestamp in microseconds\n"
           "    sample_rate: Sample rate in Hz")

      // 再生制御
      .def("play", &VideoPlayer::play, nb::sig("def play(self) -> None"),
           "Start or resume playback.")
      .def("pause", &VideoPlayer::pause, nb::sig("def pause(self) -> None"),
           "Pause playback.")
      .def("stop", &VideoPlayer::stop, nb::sig("def stop(self) -> None"),
           "Stop playback and clear queues.")

      // ウィンドウ制御
      .def("close", &VideoPlayer::close, nb::sig("def close(self) -> None"),
           "Close the window and release resources.")
      .def("poll_events", &VideoPlayer::poll_events,
           nb::sig("def poll_events(self) -> bool"),
           "Poll window events and render next frame. Returns False if window "
           "was closed.")

      // プロパティ
      .def_prop_ro("is_open", &VideoPlayer::is_open,
                   nb::sig("def is_open(self) -> bool"),
                   "Whether the window is open.")
      .def_prop_ro("is_playing", &VideoPlayer::is_playing,
                   nb::sig("def is_playing(self) -> bool"),
                   "Whether playback is active.")
      .def_prop_ro("width", &VideoPlayer::width,
                   nb::sig("def width(self) -> int"), "Window width.")
      .def_prop_ro("height", &VideoPlayer::height,
                   nb::sig("def height(self) -> int"), "Window height.")
      .def_prop_rw("title", &VideoPlayer::title, &VideoPlayer::set_title,
                   nb::sig("def title(self) -> str"),
                   nb::sig("def title(self, value: str) -> None"), "Window title.")
      .def_prop_ro("renderer_name", &VideoPlayer::renderer_name,
                   nb::sig("def renderer_name(self) -> str"),
                   "GPU renderer name (e.g., 'metal', 'vulkan').")

      // 音量制御
      .def_prop_rw("volume", &VideoPlayer::get_volume, &VideoPlayer::set_volume,
                   nb::sig("def volume(self) -> float"),
                   nb::sig("def volume(self, value: float) -> None"),
                   "Playback volume (0.0 to 1.0).")

      // キーコールバック
      .def(
          "set_key_callback", &VideoPlayer::set_key_callback,
          nb::arg("callback").none(),
          nb::sig("def set_key_callback(self, callback: typing.Callable[[int], "
                  "bool] | None) -> None"),
          "Set a callback for key events.\n\n"
          "The callback receives the key code and returns True to continue,\n"
          "or False to close the window (poll_events will return False).\n"
          "Pass None to remove the callback.\n\n"
          "Args:\n"
          "    callback: Function (key: int) -> bool, or None")

      // 統計情報
      .def("stats", &VideoPlayer::stats,
           nb::sig("def stats(self) -> dict[str, typing.Any]"),
           "Get playback statistics.\n\n"
           "Returns:\n"
           "    Dictionary with keys:\n"
           "        - video_queue_size: Number of frames in video queue\n"
           "        - audio_queue_ms: Audio queue length in milliseconds\n"
           "        - dropped_frames: Number of dropped frames\n"
           "        - repeated_frames: Number of repeated frames\n"
           "        - video_pts_us: Last rendered video PTS\n"
           "        - audio_pts_us: Current audio playback PTS\n"
           "        - sync_diff_us: Audio-video sync difference\n"
           "        - current_video_width: Current video width\n"
           "        - current_video_height: Current video height\n"
           "        - current_fps: Current FPS\n"
           "        - total_frames_enqueued: Total frames enqueued\n"
           "        - total_frames_rendered: Total frames rendered\n"
           "        - video_buffer_ms: Video buffer time in milliseconds\n"
           "        - elapsed_time_ms: Elapsed time in milliseconds\n"
           "        - video_bitrate_kbps: Video bitrate in kbps");
}
