cmake_minimum_required(VERSION 4.2)
project(raw_player LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# プラットフォームの検出
if(APPLE)
    if(NOT CMAKE_OSX_DEPLOYMENT_TARGET)
        set(CMAKE_OSX_DEPLOYMENT_TARGET "14.0" CACHE STRING "Minimum macOS deployment version")
    endif()
    message(STATUS "macOS deployment target: ${CMAKE_OSX_DEPLOYMENT_TARGET}")
elseif(UNIX AND NOT APPLE)
    message(STATUS "Building for Linux")
elseif(WIN32)
    message(STATUS "Building for Windows")
else()
    message(FATAL_ERROR "Unsupported platform")
endif()

# レイアウト: ExternalProject の依存関係は _deps 配下で管理
if(DEFINED SKBUILD_PROJECT_DIR)
    set(PROJECT_ROOT "${SKBUILD_PROJECT_DIR}")
else()
    set(PROJECT_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")
endif()

set(DEPS_DIR "${PROJECT_ROOT}/_deps")
message(STATUS "Dependencies directory: ${DEPS_DIR}")

# Python と nanobind を検索
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(nanobind CONFIG REQUIRED)

# 依存関係用の ExternalProject
include(ExternalProject)

# JSON から依存関係のバージョンを読み込み
file(READ ${CMAKE_CURRENT_SOURCE_DIR}/deps.json DEPS_JSON)

# SDL3 の設定を解析
string(JSON SDL3_TAG GET ${DEPS_JSON} sdl3 tag)
string(JSON SDL3_GIT_URL GET ${DEPS_JSON} sdl3 url)

message(STATUS "SDL3 tag: ${SDL3_TAG}")

# 静的ライブラリのビルドオプションを設定
set(BUILD_SHARED_LIBS OFF CACHE BOOL "静的ライブラリをビルド" FORCE)

# ExternalProject ビルド用の並列ビルドジョブ数を決定
if(DEFINED ENV{CMAKE_BUILD_PARALLEL_LEVEL})
    set(PARALLEL_JOBS "$ENV{CMAKE_BUILD_PARALLEL_LEVEL}")
else()
    include(ProcessorCount)
    ProcessorCount(NCORES)
    if(NOT NCORES OR NCORES EQUAL 0)
        set(NCORES 2)
    endif()
    set(PARALLEL_JOBS "${NCORES}")
endif()

# ========== SDL3 ==========
message(STATUS "Setting up SDL3...")
set(SDL3_SOURCE_DIR "${DEPS_DIR}/sdl3/${SDL3_TAG}/source")
set(SDL3_BUILD_DIR "${DEPS_DIR}/sdl3/${SDL3_TAG}/build")
set(SDL3_INSTALL_DIR "${DEPS_DIR}/sdl3/${SDL3_TAG}/install")

# Windows では .lib、それ以外では .a
if(WIN32)
    set(SDL3_LIB ${SDL3_INSTALL_DIR}/lib/SDL3-static.lib)
else()
    set(SDL3_LIB ${SDL3_INSTALL_DIR}/lib/libSDL3.a)
endif()

# プラットフォーム固有の CMake 引数 (GPU フル活用)
if(APPLE)
    set(SDL3_PLATFORM_ARGS
        -DSDL_FRAMEWORK=OFF
        # Metal (Apple GPU)
        -DSDL_METAL=ON
        -DSDL_RENDER_METAL=ON
        -DSDL_GPU=ON
        -DSDL_RENDER_GPU=ON
        # OpenGL 無効化 (Metal 優先)
        -DSDL_OPENGL=OFF
        -DSDL_OPENGLES=OFF
    )
elseif(WIN32)
    set(SDL3_PLATFORM_ARGS
        -DSDL_FORCE_STATIC_VCRT=ON
        # Vulkan (NVIDIA GPU)
        -DSDL_VULKAN=ON
        -DSDL_RENDER_VULKAN=ON
        -DSDL_GPU=ON
        -DSDL_RENDER_GPU=ON
        # Direct3D 12
        -DSDL_RENDER_D3D12=ON
    )
else()
    # Linux (NVIDIA GPU)
    set(SDL3_PLATFORM_ARGS
        -DSDL_VULKAN=ON
        -DSDL_RENDER_VULKAN=ON
        -DSDL_GPU=ON
        -DSDL_RENDER_GPU=ON
        # OpenGL 無効化 (Vulkan 優先)
        -DSDL_OPENGL=OFF
        -DSDL_OPENGLES=OFF
    )
endif()

# ビルド済みかチェック
if(EXISTS ${SDL3_LIB})
    message(STATUS "SDL3 already built: ${SDL3_LIB}")
    add_custom_target(sdl3_build)
else()
    message(STATUS "Building SDL3...")
    ExternalProject_Add(
        sdl3_build
        GIT_REPOSITORY ${SDL3_GIT_URL}
        GIT_TAG ${SDL3_TAG}
        GIT_SHALLOW TRUE
        SOURCE_DIR ${SDL3_SOURCE_DIR}
        BINARY_DIR ${SDL3_BUILD_DIR}
        STAMP_DIR ${SDL3_BUILD_DIR}/stamp
        TMP_DIR ${SDL3_BUILD_DIR}/tmp
        UPDATE_COMMAND ""
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
        CMAKE_ARGS
            -DCMAKE_INSTALL_PREFIX=${SDL3_INSTALL_DIR}
            -DCMAKE_BUILD_TYPE=Release
            -DCMAKE_POSITION_INDEPENDENT_CODE=ON
            -DCMAKE_OSX_DEPLOYMENT_TARGET=${CMAKE_OSX_DEPLOYMENT_TARGET}
            -DSDL_SHARED=OFF
            -DSDL_STATIC=ON
            -DSDL_TEST_LIBRARY=OFF
            -DSDL_TESTS=OFF
            -DSDL_EXAMPLES=OFF
            -DSDL_DISABLE_INSTALL=OFF
            -DSDL_VENDOR_INFO=libsdl-py
            ${SDL3_PLATFORM_ARGS}
        BUILD_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --config Release --parallel ${PARALLEL_JOBS}
        INSTALL_COMMAND ${CMAKE_COMMAND} --build <BINARY_DIR> --config Release --target install
        BUILD_BYPRODUCTS ${SDL3_LIB}
    )
endif()

# メインモジュールを作成
nanobind_add_module(
    raw_player_ext
    NB_STATIC
    FREE_THREADED
    src/bindings/module.cpp
    src/bindings/sdl_types.cpp
    src/bindings/audio_player.cpp
    src/bindings/video_player.cpp
)

# ビルド順序を保証するため依存関係を追加
add_dependencies(raw_player_ext sdl3_build)

# インクルードディレクトリ
target_include_directories(raw_player_ext PRIVATE
    src/bindings
    ${SDL3_INSTALL_DIR}/include
)

# ライブラリをリンク
if(WIN32)
    target_link_libraries(raw_player_ext PRIVATE
        "${SDL3_LIB}"
        winmm
        imm32
        version
        setupapi
        cfgmgr32
    )
elseif(APPLE)
    target_link_libraries(raw_player_ext PRIVATE
        ${SDL3_LIB}
        "-framework AudioToolbox"
        "-framework AVFoundation"
        "-framework Carbon"
        "-framework Cocoa"
        "-framework CoreAudio"
        "-framework CoreFoundation"
        "-framework CoreGraphics"
        "-framework CoreHaptics"
        "-framework CoreMedia"
        "-framework CoreVideo"
        "-framework ForceFeedback"
        "-framework GameController"
        "-framework IOKit"
        "-framework Metal"
        "-framework QuartzCore"
        "-framework UniformTypeIdentifiers"
    )
else()
    # Linux
    target_link_libraries(raw_player_ext PRIVATE
        ${SDL3_LIB}
        pthread
        dl
        m
    )
endif()

# 型スタブ (.pyi) ファイルの自動生成
nanobind_add_stub(
    raw_player_stub
    MODULE raw_player_ext
    OUTPUT raw_player_ext.pyi
    PYTHON_PATH $<TARGET_FILE_DIR:raw_player_ext>
    DEPENDS raw_player_ext
    MARKER_FILE py.typed
)

# Wheel に配置するためのインストール先を指定
set(PY_PACKAGE "raw_player")
install(TARGETS raw_player_ext
    LIBRARY DESTINATION ${PY_PACKAGE}
    RUNTIME DESTINATION ${PY_PACKAGE}
)

# 型スタブファイルとマーカーファイルをインストール
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/raw_player_ext.pyi DESTINATION ${PY_PACKAGE})
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/py.typed DESTINATION ${PY_PACKAGE})
