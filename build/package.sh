#!/bin/bash
# package.sh: fancypants.zip, ready to unzip into ports/, laid out the way PortMaster's
# tools/build_release.py builds it from ports/fancypants/ (metadata moved into the port
# folder, README.md renamed to fancypants.md).
# Expects the aarch64 builds in place: ports/fancypants/fancypants/ruffle (build_ruffle.sh)
# and ports/fancypants/fancypants/tools/fpa-prep (build_prep.sh).
set -e
here=$(cd "$(dirname "$0")" && pwd); root=$(cd "$here/.." && pwd)
src="$root/ports/fancypants"
for f in ruffle tools/fpa-prep; do
  [ -x "$src/fancypants/$f" ] || { echo "missing ports/fancypants/fancypants/$f, build it first"; exit 1; }
done
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp "$src/Fancy Pants Adventures.sh" "$stage/"
cp -r "$src/fancypants" "$stage/"
rm -rf "$stage/fancypants/saves" "$stage/fancypants/config" "$stage/fancypants/cache" "$stage"/fancypants/*.txt
find "$stage/fancypants/gamedata" -mindepth 1 ! -name 'Copy the Classic Pack files here.txt' -exec rm -rf {} +
cp "$src/port.json" "$src/gameinfo.xml" "$src/screenshot.png" "$stage/fancypants/"
cp "$src/README.md" "$stage/fancypants/fancypants.md"
rm -f "$root/fancypants.zip"
(cd "$stage" && zip -9 -r -q -X "$root/fancypants.zip" .)
ls -l "$root/fancypants.zip"
