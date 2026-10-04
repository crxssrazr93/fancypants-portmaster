#!/bin/bash
# package.sh: fancypants.zip, ready to unzip into ports/
# Expects the aarch64 builds in place: port/fancypants/ruffle (build_ruffle.sh)
# and port/fancypants/tools/fpa-prep (build_prep.sh).
set -e
here=$(cd "$(dirname "$0")" && pwd); root=$(cd "$here/.." && pwd)
for f in ruffle tools/fpa-prep; do
  [ -x "$root/port/fancypants/$f" ] || { echo "missing port/fancypants/$f, build it first"; exit 1; }
done
rm -f "$root/fancypants.zip"
(cd "$root/port" && zip -9 -r -q "$root/fancypants.zip" "Fancy Pants Adventures.sh" fancypants \
  -x 'fancypants/gamedata/*' -x 'fancypants/saves/*' -x 'fancypants/log.txt' -x 'fancypants/patchlog.txt' \
  && zip -q "$root/fancypants.zip" "fancypants/gamedata/Copy the Classic Pack files here.txt")
ls -l "$root/fancypants.zip"
