#!/bin/bash
# fetch_ruffle.sh [dir]: clone Ruffle at the commit the port is built from and apply the port's patches.
# Then build with: build/build_ruffle.sh <dir> work/ruffle-arm && cp work/ruffle-arm/ruffle ports/fancypants/fancypants/
set -e
here=$(cd "$(dirname "$0")" && pwd)
dir="${1:-$here/../work/ruffle-src}"
base=dcc85a1b   # Release 0.7.0-nightly.2026.10.4
[ -d "$dir/.git" ] || git clone https://github.com/ruffle-rs/ruffle.git "$dir"
git -C "$dir" checkout -q "$base"
git -C "$dir" -c user.name=port -c user.email=port@localhost am -q "$here"/ruffle-patches/*.patch
git -C "$dir" log --oneline -4
