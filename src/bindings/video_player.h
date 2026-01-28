#pragma once

#include <SDL3/SDL.h>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/string.h>

#include <deque>
#include <functional>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#ifdef __APPLE__
#include <CoreVideo/CoreVideo.h>
#endif

#include "sdl_types.h"

namespace nb = nanobind;

void init_video_player(nb::module_& m);

// 映像フレームフォーマット
enum class VideoFormat { I420, NV12, YUY2, RGBA, BGRA };

class VideoPlayer {
 public:
  // ウィンドウパラメータ付きコンストラクタ
  VideoPlayer(int width = 960,
              int height = 540,
              const std::string& title = "Raw Player");
  ~VideoPlayer();

  // === Enqueue API ===

  // I420 映像フレームをキューに追加
  // y: uint8 (H, W)、u: uint8 (H/2, W/2)、v: uint8 (H/2, W/2)
  void enqueue_video_i420(nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> y,
                          nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> u,
                          nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> v,
                          int64_t pts_us);

  // NV12 映像フレームをキューに追加
  // y: uint8 (H, W)、uv: uint8 (H/2, W)
  void enqueue_video_nv12(
      nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> y,
      nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> uv,
      int64_t pts_us);

  // NV12 映像フレームをネイティブバッファからキューに追加
  // native_buffer: PyCapsule (macOS: CVPixelBufferRef)
  void enqueue_video_nv12(nb::object native_buffer, int64_t pts_us);

  // YUY2 映像フレームをキューに追加
  // data: uint8 (H, W, 2)、パックドフォーマット Y0 U0 Y1 V0 ...
  void enqueue_video_yuy2(
      nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
      int64_t pts_us);

  // YUY2 映像フレームをネイティブバッファからキューに追加
  // native_buffer: PyCapsule (macOS: CVPixelBufferRef)
  void enqueue_video_yuy2(nb::object native_buffer, int64_t pts_us);

  // RGBA 映像フレームをキューに追加
  // data: uint8 (H, W, 4)
  void enqueue_video_rgba(
      nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
      int64_t pts_us);

  // BGRA 映像フレームをキューに追加
  // data: uint8 (H, W, 4)
  void enqueue_video_bgra(
      nb::ndarray<uint8_t, nb::c_contig, nb::device::cpu> data,
      int64_t pts_us);

  // 音声データをキューに追加
  // pcm: int16 または float32、shape は (frames, channels) または (frames,)
  void enqueue_audio(nb::ndarray<nb::c_contig, nb::device::cpu> pcm,
                     int64_t pts_us,
                     int sample_rate);

  // === 再生制御 ===
  void play();
  void pause();
  void stop();

  // === ウィンドウ制御 ===
  void close();
  bool poll_events();

  // === プロパティ ===
  bool is_open() const;
  bool is_playing() const;
  int width() const;
  int height() const;
  std::string title() const;
  void set_title(const std::string& title);
  std::string renderer_name() const;

  // === 音量制御 ===
  void set_volume(float volume);
  float get_volume() const;

  // === キーコールバック ===
  // コールバックはキーコードを受け取り、bool を返す
  // True: 継続、False: poll_events() も False を返して終了
  void set_key_callback(std::function<bool(int)> callback);

  // === 統計情報 ===
  nb::dict stats() const;

  // === キューサイズ制御 ===
  void set_max_video_queue_size(int64_t size);
  size_t get_max_video_queue_size() const;
  void drain_video();

  // === stats オーバーレイ ===
  void set_stats_overlay(bool show);
  bool get_stats_overlay() const;

 private:
  // 映像フレームのデータ構造
  struct VideoFrame {
    int64_t pts_us;      // プレゼンテーションタイムスタンプ(マイクロ秒)
    int width;           // 映像幅
    int height;          // 映像高さ
    VideoFormat format;  // フォーマット(I420/NV12/YUY2/RGBA/BGRA)
    std::vector<uint8_t>
        y_data;  // I420/NV12: Y プレーン、その他: パックドデータ
    std::vector<uint8_t>
        u_data;  // I420: U プレーン、NV12: UV プレーン、その他: 空
    std::vector<uint8_t> v_data;  // I420: V プレーン、その他: 空
  };

  // 音声チャンクのデータ構造
  struct AudioChunk {
    int64_t pts_us;             // プレゼンテーションタイムスタンプ(マイクロ秒)
    int sample_rate;            // サンプルレート
    int channels;               // チャンネル数
    bool is_float;              // true: float32、false: int16
    std::vector<uint8_t> data;  // PCM データ
  };

  // ウィンドウリソース
  SDL_Window* window_ = nullptr;
  SDL_Renderer* renderer_ = nullptr;
  SDL_Texture* texture_ = nullptr;
  int window_width_ = 960;   // ウィンドウサイズ(表示用)
  int window_height_ = 540;  // ウィンドウサイズ(表示用)
  int texture_width_ = 0;    // 現在のテクスチャサイズ(映像解像度)
  int texture_height_ = 0;   // 現在のテクスチャサイズ(映像解像度)
  VideoFormat texture_format_ = VideoFormat::I420;
  std::string title_ = "Raw Player";
  bool open_ = false;

  // 音声リソース
  SDL_AudioStream* audio_stream_ = nullptr;
  int audio_sample_rate_ = 0;
  int audio_channels_ = 0;
  bool audio_is_float_ = false;
  float volume_ = 1.0f;

  // キュー
  std::deque<VideoFrame> video_queue_;
  std::deque<AudioChunk> audio_queue_;

  // 同期状態
  int64_t audio_samples_written_ = 0;  // SDL に書き込んだ総サンプル数
  int64_t first_audio_pts_us_ = 0;     // 最初の音声チャンクの PTS
  bool audio_started_ = false;         // 音声再生が開始されたか
  int64_t last_video_pts_us_ = 0;      // 最後にレンダリングした映像の PTS
  bool playing_ = false;               // 再生中フラグ
  bool has_played_ = false;            // play() が一度でも呼ばれたか

  // 映像のみモード用のタイミング
  uint64_t video_start_time_ns_ =
      0;                             // 映像再生開始時のウォールクロック(ナノ秒)
  int64_t first_video_pts_us_ = 0;   // 最初の映像フレームの PTS
  bool video_only_started_ = false;  // 映像のみモードが開始されたか

  // 同期設定
  int64_t sync_threshold_us_ = 40000;  // 40ms の許容誤差

  // キューサイズ制限
  // 0 の場合は制限なし
  size_t max_video_queue_size_ = 5;

  // 統計情報
  int dropped_frames_ = 0;   // ドロップしたフレーム数
  int repeated_frames_ = 0;  // リピートしたフレーム数

  // 拡張統計情報
  int64_t total_frames_enqueued_ = 0;  // enqueue された総フレーム数
  int64_t total_frames_rendered_ = 0;  // レンダリングされた総フレーム数
  uint64_t play_start_time_ns_ = 0;    // play() を呼んだ時刻
  int64_t last_frame_size_bytes_ = 0;  // 最後のフレームサイズ(バイト)

  // FPS 計算用
  uint64_t fps_calc_start_ns_ = 0;  // FPS 計算開始時刻
  int fps_frame_count_ = 0;         // FPS 計算用フレームカウント
  float current_fps_ = 0.0f;        // 現在の FPS

  // stats オーバーレイ
  bool show_stats_overlay_ = false;

  // キーコールバック
  std::function<bool(int)> key_callback_;

  mutable std::mutex mutex_;

  // 内部ヘルパー
  void create_texture(int width,
                      int height,
                      VideoFormat format);  // テクスチャを作成
  void render_frame_internal(
      const VideoFrame& frame);        // フレームをレンダリング
  void process_audio_queue();          // 音声キューを処理
  int64_t get_audio_clock_us() const;  // 音声クロックを取得
  void render_next_frame();            // 次のフレームをレンダリング
  void render_stats_overlay();         // stats オーバーレイを描画
  void enqueue_frame_internal(VideoFrame&& frame);  // フレームをキューに追加
  float render_stat_line(float y, float margin, int char_size, const char* text);
};
