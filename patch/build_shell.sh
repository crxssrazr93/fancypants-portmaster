#!/bin/bash
# build_shell.sh <original ClassicPack.swf> <out.swf>
# Decompiles SuperLoaderMain from your own ClassicPack.swf, patches the source and puts it back.
set -e
here=$(cd "$(dirname "$0")" && pwd)
ffdec="${FFDEC:-$here/../work/ffdec/ffdec.jar}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
java -jar "$ffdec" -selectclass SuperLoaderMain -export script "$tmp/dec" "$1" >/dev/null
python3 "$here/patch_shell.py" "$tmp/dec/scripts/SuperLoaderMain.as" "$tmp/SuperLoaderMain.as"
java -jar "$ffdec" -replace "$1" "$2" SuperLoaderMain "$tmp/SuperLoaderMain.as"
