#!/bin/bash
# pc_sdl_run.sh <ruffle_sdl> <port dir> <WxH> <game> <level> <seconds> <out prefix> [steps...]
# Runs a PC ruffle_sdl built with tests/sdl_test_hooks.py on a private Xvfb display, straight into
# a world (game World1 to World3, level e.g. Level1), with the port's flashvars, then the steps:
# shot (saves <out prefix>-N.png), s:<seconds>, tap:<SDL key name>. DOOR=<n> picks the door.
R=$1; P=$2; RES=$3; G=$4; L=$5; T=$6; O=$7; shift 7
D=:${DNUM:-79}
Xvfb $D +extension GLX -screen 0 ${RES}x24 >/dev/null 2>&1 & XP=$!; sleep 1.5
env -u WAYLAND_DISPLAY LIBGL_ALWAYS_SOFTWARE=1 DISPLAY=$D RUFFLE_SDL_SHOT=$O.ppm RUFFLE_FPS_LOG=1 \
  RUST_LOG=warn,ruffle_core::player::port_fps=info,ruffle_sdl=info \
  "$R" --width ${RES%x*} --height ${RES#*x} --stage-scale movie --quality low \
  -Paspect=${ASPECT:-extend} -Pworldfps=30 -Pgame=$G -Plevel=$L ${DOOR:+-Pdoor=$DOOR} \
  --save-directory "$P/saves" "$P/gamedata/ClassicPack-port.swf" > "$O.log" 2>&1 & RP=$!
sleep "$T"; n=0
for st in "$@"; do
  case $st in
    shot) touch "$O.ppm.req"; sleep 1.5; magick "$O.ppm" "$O-$n.png"; n=$((n+1));;
    s:*) sleep ${st#s:};;
    tap:*) echo "${st#tap:}" > "$O.ppm.key"; sleep 0.4;;
  esac
done
kill -9 $RP 2>/dev/null; kill $XP 2>/dev/null; wait 2>/dev/null
