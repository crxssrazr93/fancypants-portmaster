#!/bin/bash
# build_ruffle.sh <ruffle-src-dir> <out-dir>
# Builds a slim Ruffle for aarch64: no OpenSSL (rustls), no fontconfig/freetype,
# no OpenH264 download, ATF textures are converted to PNG by the port instead.
# Tuned for the Cortex-A53 CPUs of the target handhelds (LTO measured no gain).
set -e
src=$(realpath "$1"); out=$(realpath -m "$2"); here=$(cd "$(dirname "$0")" && pwd)
cache="${CARGO_CACHE:-$here/../work/.cargo-cache}"; mkdir -p "$out" "$cache"
docker build -q -t fpa-ruffle-cross "$here"
# use rustls instead of native-tls (avoid libssl.so.* version mismatches across CFWs)
sed -i 's|^ruffle_frontend_utils = { path = "../frontend-utils", features = \["cpal", "fs", "navigator"\] }|ruffle_frontend_utils = { path = "../frontend-utils", default-features = false, features = ["cpal", "fs", "navigator", "rustls-tls"] }|' "$src/desktop/Cargo.toml"
grep -q 'rustls-tls"\] }' "$src/desktop/Cargo.toml"
docker run --rm -v "$src":/src -v "$(realpath "$cache")":/root/.cargo/registry -v "$out":/out fpa-ruffle-cross bash -c '
  export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C target-cpu=cortex-a53" &&
  cargo build --release -p ruffle_desktop --target aarch64-unknown-linux-gnu \
    --no-default-features --features software_video,lzma &&
  aarch64-linux-gnu-strip -o /out/ruffle target/aarch64-unknown-linux-gnu/release/ruffle_desktop'
