#!/bin/bash
# pc_run.sh <ruffle> <portdir> <seconds> <out-prefix> [steps: shot | sleep:<s> | xdotool args]
R=$1; P=$2; T=$3; O=$4; shift 4
Xvfb :78 -screen 0 ${XRES:-640x480}x24 >/dev/null 2>&1 & XP=$!; sleep 1.5
DISPLAY=:78 WAYLAND_DISPLAY= "$R" --no-gui --fullscreen -g gl -p low --gamemode off \
  --player-runtime air --filesystem-access-mode allow --open-url-mode deny --tcp-connections deny \
  --quality low --letterbox ${LETTERBOX:-on} --save-directory "$P/saves" --config "$P/config" --cache-directory "$P/cache" \
  $RUFFLE_EXTRA "$P/gamedata/ClassicPack-port.swf" > "$O.log" 2>&1 & RP=$!
sleep "$T"
n=0
for step in "$@"; do
  case $step in
    shot) DISPLAY=:78 import -window root "$O-$n.png"; n=$((n+1));;
    sleep:*) sleep ${step#sleep:};;
    *) DISPLAY=:78 xdotool $step;;
  esac
done
DISPLAY=:78 import -window root "$O.png"
kill $RP 2>/dev/null; wait $RP 2>/dev/null; kill $XP; wait $XP 2>/dev/null
