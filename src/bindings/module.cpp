#include <SDL3/SDL.h>
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <stdexcept>
#include <vector>

#include "audio_player.h"
#include "sdl_types.h"
#include "video_player.h"

namespace nb = nanobind;

// 前方宣言
void init_sdl_types(nb::module_& m);
void init_audio_player(nb::module_& m);
void init_video_player(nb::module_& m);

// SDL 初期化状態
static bool sdl_initialized = false;

// SDL を初期化(未初期化の場合のみ)
static void ensure_sdl_init() {
  if (!sdl_initialized) {
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO)) {
      throw std::runtime_error(std::string("Failed to initialize SDL: ") +
                               SDL_GetError());
    }
    sdl_initialized = true;
  }
}

// SDL をクリーンアップ
static void cleanup_sdl() {
  if (sdl_initialized) {
    SDL_Quit();
    sdl_initialized = false;
  }
}

NB_MODULE(_raw_player_py, m) {
  m.doc() = "Raw audio and video playback bindings for Python";

  // モジュールインポート時に SDL を初期化
  ensure_sdl_init();

  // クリーンアップ関数を登録
  auto atexit = nb::module_::import_("atexit");
  atexit.attr("register")(nb::cpp_function([]() { cleanup_sdl(); }));

  // 型バインディングを初期化
  init_sdl_types(m);

  // プレイヤークラスを初期化
  init_audio_player(m);
  init_video_player(m);

  // モジュールレベル関数
  m.def(
      "get_version",
      []() {
        return std::string("SDL ") + std::to_string(SDL_MAJOR_VERSION) + "." +
               std::to_string(SDL_MINOR_VERSION) + "." +
               std::to_string(SDL_MICRO_VERSION);
      },
      "Get the SDL version string.");

  m.def(
      "get_audio_driver",
      []() -> std::string {
        const char* driver = SDL_GetCurrentAudioDriver();
        return driver ? std::string(driver) : "";
      },
      "Get the current audio driver name.");

  m.def(
      "get_video_driver",
      []() -> std::string {
        const char* driver = SDL_GetCurrentVideoDriver();
        return driver ? std::string(driver) : "";
      },
      "Get the current video driver name.");

  m.def(
      "get_gpu_driver",
      []() -> std::string {
        const char* driver = SDL_GetGPUDriver(0);
        return driver ? std::string(driver) : "";
      },
      "Get the primary GPU driver name (e.g., 'metal', 'vulkan', 'd3d12').");

  m.def(
      "get_num_gpu_drivers", []() -> int { return SDL_GetNumGPUDrivers(); },
      "Get the number of available GPU drivers.");

  m.def(
      "get_all_gpu_drivers",
      []() -> std::vector<std::string> {
        std::vector<std::string> drivers;
        int count = SDL_GetNumGPUDrivers();
        for (int i = 0; i < count; i++) {
          const char* driver = SDL_GetGPUDriver(i);
          if (driver) {
            drivers.push_back(std::string(driver));
          }
        }
        return drivers;
      },
      "Get all available GPU driver names.");
}
