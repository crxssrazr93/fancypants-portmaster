#!/bin/bash
# build_world_as2.sh <original FPAWorldN.swf> <out.swf>   (N = 1, 2 or 3)
set -e
here=$(cd "$(dirname "$0")" && pwd)
ffdec="${FFDEC:-$here/../work/ffdec/ffdec.jar}"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
java -jar "$ffdec" -format script:pcode -export script "$tmp/exp" "$1" >/dev/null
python3 "$here/patch_world_as2.py" "$tmp/exp" "$tmp" > "$tmp/list"
args=()
while IFS=$'\t' read -r name file; do args+=("$name" "$file"); done < "$tmp/list"
java -jar "$ffdec" -replace "$1" "$2" "${args[@]}"
