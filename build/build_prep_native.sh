#!/bin/bash
# build_prep_native.sh <out-dir>: cross-compile tools/fpa-prep for aarch64 without Docker, with host clang
# + lld against a Debian bullseye arm64 sysroot (glibc 2.31), like build_ruffle_native.sh.
# SYSROOT defaults to ~/chroot-bullseye.
set -e
here=$(cd "$(dirname "$0")" && pwd); out=$(realpath -m "$1"); mkdir -p "$out"
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
  AR_aarch64_unknown_linux_gnu=llvm-ar
cd "$here/../tools/fpa-prep"
CARGO_TARGET_DIR=${CARGO_TARGET_DIR:-$HOME/fpa-out/prep-aarch64} cargo build --release --target aarch64-unknown-linux-gnu
cp "${CARGO_TARGET_DIR:-$HOME/fpa-out/prep-aarch64}/aarch64-unknown-linux-gnu/release/fpa-prep" "$out/"
echo "glibc: $(llvm-objdump -T "$out/fpa-prep" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -1)"
