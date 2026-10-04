#!/bin/bash
# build_prep.sh <out-dir>: cross-compile tools/fpa-prep for aarch64 (glibc 2.31 image)
set -e
here=$(cd "$(dirname "$0")" && pwd); out=$(realpath -m "$1")
cache="${CARGO_CACHE:-$here/../work/.cargo-cache}"; mkdir -p "$out" "$cache"
docker build -q -t fpa-ruffle-cross "$here"
docker run --rm -v "$here/../tools/fpa-prep":/src -v "$(realpath "$cache")":/root/.cargo/registry -v "$out":/out fpa-ruffle-cross bash -c '
  CARGO_TARGET_DIR=/tmp/t cargo build --release --target aarch64-unknown-linux-gnu &&
  cp /tmp/t/aarch64-unknown-linux-gnu/release/fpa-prep /out/ && chown '"$(id -u):$(id -g)"' /out/fpa-prep'
