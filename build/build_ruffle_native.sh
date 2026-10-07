#!/bin/bash
# build_ruffle_native.sh <ruffle-src-dir> <out-dir>: build/build_ruffle.sh without Docker. Cross-compiles
# ruffle_sdl for aarch64 with host clang + lld against a Debian bullseye arm64 sysroot (glibc 2.31,
# libsdl2-dev and libasound2-dev installed in it), with the same cargo command and features as the
# Docker build. Needs rustup, clang, lld and llvm-ar/llvm-strip/llvm-objdump on the host.
# SYSROOT defaults to ~/chroot-bullseye (e.g. debootstrap --arch=arm64 bullseye, then
# apt-get install libsdl2-dev libasound2-dev inside it).
set -e
src=$(realpath "$1"); out=$(realpath -m "$2"); mkdir -p "$out"
SYSROOT=${SYSROOT:-$HOME/chroot-bullseye}
source "$HOME/.cargo/env"
rustup target add aarch64-unknown-linux-gnu >/dev/null
wrap=$out/.cc; mkdir -p "$wrap"
for t in cc c++; do
  drv=clang; [ $t = c++ ] && drv=clang++
  printf '#!/bin/sh\nexec %s --target=aarch64-linux-gnu --sysroot=%s -fuse-ld=lld "$@"\n' "$drv" "$SYSROOT" > "$wrap/$t"
  chmod +x "$wrap/$t"
done
export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=$wrap/cc \
  CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_RUSTFLAGS="-C target-cpu=cortex-a53" \
  CC_aarch64_unknown_linux_gnu=$wrap/cc CXX_aarch64_unknown_linux_gnu=$wrap/c++ \
  AR_aarch64_unknown_linux_gnu=llvm-ar \
  PKG_CONFIG_ALLOW_CROSS=1 PKG_CONFIG_SYSROOT_DIR=$SYSROOT \
  PKG_CONFIG_LIBDIR=$SYSROOT/usr/lib/aarch64-linux-gnu/pkgconfig:$SYSROOT/usr/share/pkgconfig \
  BINDGEN_EXTRA_CLANG_ARGS_aarch64_unknown_linux_gnu="--target=aarch64-linux-gnu --sysroot=$SYSROOT"
cd "$src"
cargo build --release -p ruffle_sdl --target aarch64-unknown-linux-gnu --features lzma
llvm-strip -o "$out/ruffle_sdl" "${CARGO_TARGET_DIR:-target}/aarch64-unknown-linux-gnu/release/ruffle_sdl"
echo "glibc: $(llvm-objdump -T "$out/ruffle_sdl" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1)"
llvm-readelf -d "$out/ruffle_sdl" | grep NEEDED
