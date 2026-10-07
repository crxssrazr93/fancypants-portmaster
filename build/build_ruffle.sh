#!/bin/bash
# build_ruffle.sh <ruffle-src-dir> <out-dir>
# Builds ruffle_sdl (Ruffle on SDL2 + GLES 3, the sdl/ crate added by build/ruffle-patches) for aarch64:
# no X11, Wayland or Westonpack needed, no OpenSSL, no fontconfig/freetype, no OpenH264 download
# (ATF textures are converted to PNG by the port instead). Links only libSDL2, libasound and glibc.
# Tuned for the Cortex-A53 CPUs of the target handhelds (LTO measured no gain).
# Without Docker: build/build_ruffle_native.sh (same cargo command, host clang + a Debian sysroot).
set -e
src=$(realpath "$1"); out=$(realpath -m "$2"); here=$(cd "$(dirname "$0")" && pwd)
cache="${CARGO_CACHE:-$here/../work/.cargo-cache}"; mkdir -p "$out" "$cache"
docker build -q -t fpa-ruffle-cross "$here"
# -L: libSDL2.so comes from libsdl2-dev:arm64 in the multiarch directory (sdl2-sys links -lSDL2
# without pkg-config)
docker run --rm -v "$src":/src -v "$(realpath "$cache")":/root/.cargo/registry -v "$out":/out fpa-ruffle-cross bash -c '
  export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C target-cpu=cortex-a53 -L native=/usr/lib/aarch64-linux-gnu" &&
  cargo build --release -p ruffle_sdl --target aarch64-unknown-linux-gnu --features lzma &&
  aarch64-linux-gnu-strip -o /out/ruffle_sdl target/aarch64-unknown-linux-gnu/release/ruffle_sdl'
