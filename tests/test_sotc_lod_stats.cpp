// SPDX-License-Identifier: GPL-2.0-or-later
#include <cassert>
#include <cstdio>
#include "video_core/sotc_lod_stats.h"

int main() {
    // Run with the normal default: no linger, mip 2, no keep override.
    assert(std::getenv("SOTC_LOD_LINGER") == nullptr);
    assert(std::getenv("SOTC_LOD_LEVEL") == nullptr);
    assert(std::getenv("SOTC_LOD_KEEP") == nullptr);
    u64 entries[256]{};
    SotcLod::Mark(7);
    SotcLod::Mark(7);
    SotcLod::Collect(entries);
    assert(((entries[7] >> 56) & 15) == 2);
    assert(((entries[7] >> 32) & 0xffffff) == 512);
    assert(((entries[8] >> 56) & 15) == 15);
    SotcLod::Collect(entries);
    assert(((entries[7] >> 56) & 15) == 15);
    SotcLod::Mark(7);
    SotcLod::Collect(entries);
    assert(((entries[7] >> 56) & 15) == 2);
    assert(((entries[7] >> 32) & 0xffffff) == 256);
    std::puts("PASS: sampled textures survive linger=0; unused banks expire immediately");
}
