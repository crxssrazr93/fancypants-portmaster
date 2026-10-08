#!/bin/bash
# world4_manifest.sh <Classic Pack folder>
# Lists World 4's level SWFs, ATF textures and atlas XMLs with their MD5s (no game content) in
# ports/fancypants/fancypants/tools/patch/world4_files.txt, which the setup checks so a missing or
# different file stops it with a clear message. make_patches.sh runs it.
set -e
here=$(cd "$(dirname "$0")" && pwd)
out="$here/../ports/fancypants/fancypants/tools/patch/world4_files.txt"
cd "$1"
find World4/Levels World4/assets -type f \( -name "*.swf" -o -name "*.atf" -o -name "*.xml" \) | LC_ALL=C sort |
  while IFS= read -r f; do echo "$(md5sum "$f" | cut -d' ' -f1) $f"; done > "$out"
echo "$(wc -l < "$out") World 4 files listed in $out"
