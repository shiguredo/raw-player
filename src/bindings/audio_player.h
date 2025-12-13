#pragma once

#include <SDL3/SDL.h>
#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>

#include <deque>
#include <mutex>
#include <vector>

namespace nb = nanobind;

void init_audio_player(nb::module_& m);

class AudioPlayer {
 public:
  AudioPlayer();
  ~AudioPlayer();

  // === Enqueue API ===

  // 音声データをキューに追加
  // pcm: int16 または float32、shape は (frames, channels) または (frames,)
  void enqueue_audio(nb::ndarray<nb::c_contig, nb::device::cpu> pcm,
                     int64_t pts_us,
                     int sample_rate);

  // === 再生制御 ===
  void play();
  void pause();
  void stop();

  // === プロパティ ===
  bool is_playing() const;

  // === 音量制御 ===
  void set_volume(float volume);
  float get_volume() const;

  // === 統計情報 ===
  nb::dict stats() const;

 private:
  // 音声チャンクのデータ構造
  struct AudioChunk {
    int64_t pts_us;   // プレゼンテーションタイムスタンプ(マイクロ秒)
    int sample_rate;  // サンプルレート
    int channels;     // チャンネル数
    bool is_float;    // true: float32、false: int16
    std::vector<uint8_t> data;  // PCM データ
  };

  // 音声リソース
  SDL_AudioStream* audio_stream_ = nullptr;
  int audio_sample_rate_ = 0;
  int audio_channels_ = 0;
  bool audio_is_float_ = false;
  float volume_ = 1.0f;

  // キュー
  std::deque<AudioChunk> audio_queue_;

  // 同期状態
  int64_t audio_samples_written_ = 0;  // SDL に書き込んだ総サンプル数
  int64_t first_audio_pts_us_ = 0;     // 最初の音声チャンクの PTS
  bool audio_started_ = false;         // 音声再生が開始されたか
  bool playing_ = false;               // 再生中フラグ

  // 統計情報
  int chunks_played_ = 0;  // 再生したチャンク数

  // 拡張統計情報
  int64_t total_samples_enqueued_ = 0;  // enqueue された総サンプル数
  uint64_t play_start_time_ns_ = 0;     // play() を呼んだ時刻

  mutable std::mutex mutex_;

  // 内部ヘルパー
  void process_audio_queue();          // キューを処理して SDL に送信
  int64_t get_audio_clock_us() const;  // 現在の音声クロックを取得
};
