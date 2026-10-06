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

# Knulli names the buttons for games by position, as SDL does: "a" is the bottom button, which
# is labelled B on these devices. Swap a/b and x/y so the buttons act as labelled, like in the
# system menus.
if [ "$CFW_NAME" = "knulli" ]; then
  swap_ab() { sed -E 's/,a:/,@:/g; s/,b:/,a:/g; s/,@:/,b:/g; s/,x:/,@:/g; s/,y:/,x:/g; s/,@:/,y:/g'; }
  export SDL_GAMECONTROLLERCONFIG="$(printf '%s\n' "$SDL_GAMECONTROLLERCONFIG" | swap_ab)"
  swap_ab < "$SDL_GAMECONTROLLERCONFIG_FILE" > /tmp/gamecontrollerdb_ab.txt &&
    export SDL_GAMECONTROLLERCONFIG_FILE=/tmp/gamecontrollerdb_ab.txt
fi

GAMEDIR="/$directory/ports/fancypants"
DATADIR="$GAMEDIR/gamedata"
cd "$GAMEDIR"

> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1
# Device, system and memory details for bug reports (tools/portlog.sh)
# The files a bug report needs; named in log.txt and on screen only when something fails
export PORT_REPORT_FILES="ports/fancypants/log.txt and patchlog.txt"
source "$GAMEDIR/tools/portlog.sh"
port_header "Fancy Pants Adventures launcher"

$ESUDO chmod +x "$GAMEDIR/ruffle" "$GAMEDIR/tools/fpa-prep" "$GAMEDIR/tools/patchscript" "$GAMEDIR/tools/run-ruffle"

# User settings: quality, aspect mode, frame rate, GL mode
source "$GAMEDIR/fancypants.cfg"

# Patch the Steam files for Ruffle on first run, and again when a port update ships new patches
PATCH_VERSION="$(cat "$GAMEDIR/tools/patch/version")"
port_files "$DATADIR/ClassicPack.swf" "$DATADIR/ClassicPack-port.swf"
port_log "setup: patch version $PATCH_VERSION, prepared $(cat "$DATADIR/.port_prepared" 2>/dev/null || echo never)"
port_log "settings (fancypants.cfg): quality $FPA_QUALITY, aspect $FPA_ASPECT, world fps $FPA_WORLD_FPS, GL $FPA_GL_LIBRARY, fps log $FPA_FPS_LOG"
if [ "$(cat "$DATADIR/.port_prepared" 2>/dev/null)" != "$PATCH_VERSION" ]; then
  if [ -f "$controlfolder/utils/patcher.txt" ]; then
    export PATCHER_FILE="$GAMEDIR/tools/patchscript"
    export PATCHER_GAME="$(basename "${0%.*}")"
    export PATCHER_TIME="a few minutes"
    export controlfolder
    port_log "running the setup (tools/patchscript), its log is patchlog.txt"
    source "$controlfolder/utils/patcher.txt"
  else
    pm_message "This port requires the latest version of PortMaster."
    sleep 5
    pm_finish
    exit 1
  fi
  # the patcher screen has shown the error already; patchlog.txt keeps it
  if [ "$(cat "$DATADIR/.port_prepared" 2>/dev/null)" != "$PATCH_VERSION" ]; then
    port_log "setup failed"
    port_report
    pm_message "Preparing the game failed, see ports/fancypants/patchlog.txt. To report it, send $PORT_REPORT_FILES."
    sleep 8
    pm_finish
    exit 1
  fi
fi

# Mount Weston runtime
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
port_mounted "$weston_runtime" "$weston_dir/westonwrap.sh"

mkdir -p "$GAMEDIR/saves" "$GAMEDIR/config" "$GAMEDIR/cache"

# gptokeyb is unresponsive on muOS (see the Dicey Dungeons port)
if [ "$CFW_NAME" = "muOS" ] && [ -n "$GPTOKEYB2" ]; then
  $GPTOKEYB2 "ruffle" -c "$GAMEDIR/fancypants.gptk" &
else
  $GPTOKEYB "ruffle" -c "$GAMEDIR/fancypants.gptk" &
fi
pm_platform_helper "$GAMEDIR/ruffle"

# westonwrap replaces XDG_RUNTIME_DIR; pass the real one on so ALSA can reach PipeWire
REAL_XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
# FPA_FPS_LOG=1 in fancypants.cfg writes the frame rate to log.txt
[ "$FPA_FPS_LOG" = "1" ] && FPS_ENV="RUFFLE_FPS_LOG=1"

port_log "starting the game, quality $FPA_QUALITY, aspect $FPA_ASPECT, world fps $FPA_WORLD_FPS, GL $FPA_GL_LIBRARY"
# CRUSTY_BLOCK_INPUT: gptokeyb provides the keyboard, so don't also forward the pad
# WRAPPED_PRELOAD_PANFROST: on ROCKNIX/panfrost westonwrap runs the app natively; preload crusty for input blocking
# WGPU_DISCARD_HAL_LABELS: avoids a libmali crash in glPushDebugGroup (gfx-rs/wgpu#8937)
# run-ruffle restarts Ruffle when the game switches worlds, so only one world is in memory
$ESUDO env CRUSTY_BLOCK_INPUT=1 \
  WRAPPED_PRELOAD_PANFROST="$weston_dir/lib_aarch64/graphics/sdl_cursor/libcrusty.so" \
  $weston_dir/westonwrap.sh headless noop kiosk "$FPA_GL_LIBRARY" \
  WAYLAND_DISPLAY= HOME="$GAMEDIR/config" XDG_CONFIG_HOME="$GAMEDIR/config" XDG_DATA_HOME="$GAMEDIR/config" \
  XDG_CACHE_HOME="$GAMEDIR/cache" XDG_RUNTIME_DIR="$REAL_XDG_RUNTIME_DIR" \
  RUST_LOG=warn,ruffle_core::player::port_fps=info $FPS_ENV WGPU_DISCARD_HAL_LABELS=1 \
  "$GAMEDIR/tools/run-ruffle" "$GAMEDIR/ruffle" --no-gui --fullscreen -g gl -p low --gamemode off \
    --player-runtime air --filesystem-access-mode allow --open-url-mode deny --tcp-connections deny \
    --quality "$FPA_QUALITY" --letterbox off -Paspect="$FPA_ASPECT" -Pworldfps="$FPA_WORLD_FPS" \
    --width "$DISPLAY_WIDTH" --height "$DISPLAY_HEIGHT" \
    --save-directory "$GAMEDIR/saves" --config "$GAMEDIR/config" --cache-directory "$GAMEDIR/cache" \
    "$DATADIR/ClassicPack-port.swf"

# Clean up after ourselves
port_exit
$ESUDO $weston_dir/westonwrap.sh cleanup
if [[ "$PM_CAN_MOUNT" != "N" ]]; then
  $ESUDO umount "${weston_dir}"
fi
pm_finish
