#pragma once

#include <nanobind/nanobind.h>

#include <cstdint>

namespace nb = nanobind;

// 前方宣言
void init_sdl_types(nb::module_& m);
