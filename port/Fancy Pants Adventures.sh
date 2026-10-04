#!/bin/bash

XDG_DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}

if [ -d "/opt/system/Tools/PortMaster/" ]; then
  controlfolder="/opt/system/Tools/PortMaster"
elif [ -d "/opt/tools/PortMaster/" ]; then
  controlfolder="/opt/tools/PortMaster"
elif [ -d "$XDG_DATA_HOME/PortMaster/" ]; then
  controlfolder="$XDG_DATA_HOME/PortMaster"
else
  controlfolder="/roms/ports/PortMaster"
fi

source $controlfolder/control.txt
[ -f "${controlfolder}/mod_${CFW_NAME}.txt" ] && source "${controlfolder}/mod_${CFW_NAME}.txt"
get_controls

GAMEDIR="/$directory/ports/fancypants"
DATADIR="$GAMEDIR/gamedata"
cd "$GAMEDIR"

> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1

$ESUDO chmod +x "$GAMEDIR/ruffle" "$GAMEDIR/tools/fpa-prep" "$GAMEDIR/tools/patchscript" "$GAMEDIR/tools/run-ruffle.sh"

# Optional user settings (quality, renderer); see fancypants.cfg
FPA_QUALITY="low"
FPA_ASPECT="extend"
FPA_WORLD_FPS="30"
FPA_GL_LIBRARY="crusty_x11egl"
FPA_FPS_LOG="0"
[ -f "$GAMEDIR/fancypants.cfg" ] && source "$GAMEDIR/fancypants.cfg"
# FPA_FPS_LOG=1 writes frame rate and timings to log.txt every two seconds
FPS_ENV="RUFFLE_FPS_LOG_OFF=1"
[ "$FPA_FPS_LOG" = "1" ] && FPS_ENV="RUFFLE_FPS_LOG=1"

# First run (or after a port update): patch the Classic Pack for Ruffle and convert World 4's textures
PORT_PATCH_VERSION="$(cat "$GAMEDIR/tools/patch/version")"
if [ "$(cat "$DATADIR/.port_prepared" 2>/dev/null)" != "$PORT_PATCH_VERSION" ]; then
  if [ -f "$controlfolder/utils/patcher.txt" ]; then
    export PATCHER_FILE="$GAMEDIR/tools/patchscript"
    export PATCHER_GAME="$(basename "${0%.*}")"
    export PATCHER_TIME="about 2 minutes"
    export controlfolder
    export ESUDO
    source "$controlfolder/utils/patcher.txt"
    $ESUDO kill -9 $(pidof gptokeyb) 2>/dev/null
  else
    pm_message "Preparing game files, this takes a few minutes..."
    bash "$GAMEDIR/tools/patchscript"
  fi
  if [ "$(cat "$DATADIR/.port_prepared" 2>/dev/null)" != "$PORT_PATCH_VERSION" ]; then
    pm_message "Game files could not be prepared. See $GAMEDIR/patchlog.txt"
    sleep 5
    exit 1
  fi
fi

# Mount Weston runtime (Ruffle needs an X11/Wayland window and EGL)
weston_dir=/tmp/weston
$ESUDO mkdir -p "${weston_dir}"
weston_runtime="weston_pkg_0.2"
if [ ! -f "$controlfolder/libs/${weston_runtime}.squashfs" ]; then
  if [ ! -f "$controlfolder/harbourmaster" ]; then
    pm_message "This port requires the latest PortMaster to run, please go to https://portmaster.games/ for more info."
    sleep 5
    exit 1
  fi
  $ESUDO $controlfolder/harbourmaster --quiet --no-check runtime_check "${weston_runtime}.squashfs"
fi
if [[ "$PM_CAN_MOUNT" != "N" ]]; then
  $ESUDO umount "${weston_dir}"
fi
$ESUDO mount "$controlfolder/libs/${weston_runtime}.squashfs" "${weston_dir}"

mkdir -p "$GAMEDIR/saves" "$GAMEDIR/config" "$GAMEDIR/cache"

# gptokeyb1 is unresponsive on muOS (see the Dicey Dungeons port)
if [ "$CFW_NAME" = "muOS" ] && [ -n "$GPTOKEYB2" ]; then
  $GPTOKEYB2 "ruffle" -c "$GAMEDIR/fancypants.gptk" &
else
  $GPTOKEYB "ruffle" -c "$GAMEDIR/fancypants.gptk" &
fi
# westonwrap replaces XDG_RUNTIME_DIR; keep the real one so ALSA can reach PipeWire
REAL_XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
pm_platform_helper "$GAMEDIR/ruffle"

# CRUSTY_BLOCK_INPUT: gptokeyb provides the keyboard, so don't also forward the pad
# WGPU_DISCARD_HAL_LABELS: avoids a libmali crash in glPushDebugGroup (gfx-rs/wgpu#8937)
# On ROCKNIX/panfrost westonwrap runs the app natively, so preload crusty there for input blocking
$ESUDO env CRUSTY_BLOCK_INPUT=1 WRAPPED_LIBRARY_PATH="$GAMEDIR/libs.${DEVICE_ARCH}:$LD_LIBRARY_PATH" \
  WRAPPED_PRELOAD_PANFROST="$weston_dir/lib_aarch64/graphics/sdl_cursor/libcrusty.so" \
  $weston_dir/westonwrap.sh headless noop kiosk "$FPA_GL_LIBRARY" \
  WAYLAND_DISPLAY= HOME="$GAMEDIR/config" XDG_CONFIG_HOME="$GAMEDIR/config" XDG_DATA_HOME="$GAMEDIR/config" \
  XDG_CACHE_HOME="$GAMEDIR/cache" XDG_RUNTIME_DIR="$REAL_XDG_RUNTIME_DIR" RUST_LOG=warn,ruffle_core::player::port_fps=info $FPS_ENV RUST_BACKTRACE=1 WGPU_DISCARD_HAL_LABELS=1 \
  "$GAMEDIR/tools/run-ruffle.sh" "$GAMEDIR/ruffle" --no-gui --fullscreen -g gl -p low --gamemode off \
    --player-runtime air --filesystem-access-mode allow --open-url-mode deny --tcp-connections deny \
    --quality "$FPA_QUALITY" --letterbox off -Paspect="$FPA_ASPECT" -Pworldfps="$FPA_WORLD_FPS" --width "$DISPLAY_WIDTH" --height "$DISPLAY_HEIGHT" \
    --save-directory "$GAMEDIR/saves" --config "$GAMEDIR/config" --cache-directory "$GAMEDIR/cache" \
    "$DATADIR/ClassicPack-port.swf"

# Clean up after ourselves
$ESUDO $weston_dir/westonwrap.sh cleanup
if [[ "$PM_CAN_MOUNT" != "N" ]]; then
  $ESUDO umount "${weston_dir}"
fi
pm_finish
