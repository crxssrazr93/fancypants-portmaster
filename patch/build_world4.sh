#!/bin/bash
# build_world4.sh <original FPAWorld4.swf> <World4 dir> <out.swf> [scale]
set -e
here=$(cd "$(dirname "$0")" && pwd)
ffdec="${FFDEC:-$here/../work/ffdec/ffdec.jar}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
java -jar "$ffdec" -selectclass Main,StarlingBackgrounds,starling.textures.ConcretePotTexture -export script "$tmp/dec" "$1" >/dev/null
mkdir -p "$tmp/out"
python3 "$here/patch_world4.py" "$tmp/dec/scripts" "$2" "$tmp/out" "${4:-0.5}"
java -jar "$ffdec" -replace "$1" "$3" Main "$tmp/out/Main.as" StarlingBackgrounds "$tmp/out/StarlingBackgrounds.as" starling.textures.ConcretePotTexture "$tmp/out/starling/textures/ConcretePotTexture.as"
