#!/bin/bash
# make_patches.sh <Classic Pack folder>
# Builds the xdelta3 patches in port/fancypants/tools/patch/ from your own Steam files.
# Needs Java (for JPEXS ffdec, path in $FFDEC), Python 3 and Docker.
# Remember to raise port/fancypants/tools/patch/version when the patches change,
# so prepared installs patch again.
set -e
here=$(cd "$(dirname "$0")" && pwd); root="$here/.."
game=$(realpath "$1")
out="$root/port/fancypants/tools/patch"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/built" "$tmp/fws/orig" "$tmp/fws/new"

"$root/patch/build_shell.sh" "$game/ClassicPack.swf" "$tmp/built/ClassicPack.swf"
for n in 1 2 3; do
  "$root/patch/build_world_as2.sh" "$game/World$n/FPAWorld$n.swf" "$tmp/built/FPAWorld$n.swf"
done
"$root/patch/build_world4.sh" "$game/World4/FPAWorld4.swf" "$game/World4" "$tmp/built/FPAWorld4.swf" 0.5

# the patches apply to uncompressed SWFs (the device inflates the originals first)
for f in ClassicPack World1/FPAWorld1 World2/FPAWorld2 World3/FPAWorld3 World4/FPAWorld4; do
  b=$(basename "$f")
  python3 "$root/patch/swf_inflate.py" "$game/$f.swf" "$tmp/fws/orig/$b.swf"
  python3 "$root/patch/swf_inflate.py" "$tmp/built/$b.swf" "$tmp/fws/new/$b.swf"
done

# -S none: PortMaster's xdelta3 has no LZMA secondary compression
docker run --rm --platform linux/amd64 -v "$tmp/fws":/w:ro -v "$out":/out alpine sh -c '
  apk add -q xdelta3 &&
  for f in ClassicPack FPAWorld1 FPAWorld2 FPAWorld3 FPAWorld4; do
    xdelta3 -e -9 -S none -f -s /w/orig/$f.swf /w/new/$f.swf /out/$f.xdelta &&
    xdelta3 -d -f -s /w/orig/$f.swf /out/$f.xdelta /tmp/t && cmp /tmp/t /w/new/$f.swf || exit 1
  done
  chown '"$(id -u):$(id -g)"' /out/*.xdelta'
echo "patches written to $out"
