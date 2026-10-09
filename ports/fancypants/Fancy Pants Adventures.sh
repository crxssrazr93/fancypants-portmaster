#!/bin/bash
# PORTMASTER: fancypants.zip, Fancy Pants Adventures.sh

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

# the previous run's log is kept as log.prev.txt
mv -f "$GAMEDIR/log.txt" "$GAMEDIR/log.prev.txt" 2>/dev/null
> "$GAMEDIR/log.txt" && exec > >(tee "$GAMEDIR/log.txt") 2>&1
# Device, system and memory details for bug reports (tools/portlog.sh)
# The files a bug report needs; named in log.txt and on screen only when something fails
export PORT_REPORT_FILES="ports/fancypants/log.txt and patchlog.txt"
source "$GAMEDIR/tools/portlog.sh"
port_header "Fancy Pants Adventures launcher"

$ESUDO chmod +x "$GAMEDIR/ruffle_sdl" "$GAMEDIR/tools/fpa-prep" "$GAMEDIR/tools/patchscript" "$GAMEDIR/tools/run-ruffle"

# User settings: quality, aspect mode, frame rate
source "$GAMEDIR/fancypants.cfg"

# Patch the Steam files for Ruffle on first run, and again when a port update ships new patches
PATCH_VERSION="$(cat "$GAMEDIR/tools/patch/version")"
port_files "$DATADIR/ClassicPack.swf" "$DATADIR/ClassicPack-port.swf"
port_log "setup: patch version $PATCH_VERSION, prepared $(head -n 1 "$DATADIR/.port_prepared" 2>/dev/null || echo never)"
# prepared: this patch version, and the files the setup wrote unchanged since (a fresh copy of the
# game, or an update, changes them)
prepared() { [ "$(cat "$DATADIR/.port_prepared" 2>/dev/null)" = "$(echo "$PATCH_VERSION"; cd "$DATADIR" && fpa_stamp)" ]; }
port_log "settings (fancypants.cfg): quality $FPA_QUALITY, aspect $FPA_ASPECT, world fps $FPA_WORLD_FPS, fps log $FPA_FPS_LOG"
if ! prepared; then
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
  if ! prepared; then
    port_log "setup failed"
    port_report
    pm_message "Preparing the game failed, see ports/fancypants/patchlog.txt. To report it, send $PORT_REPORT_FILES."
    sleep 8
    pm_finish
    exit 1
  fi
fi

mkdir -p "$GAMEDIR/saves"

# gptokeyb is unresponsive on muOS, so gptokeyb2 is used there
if [ "$CFW_NAME" = "muOS" ] && [ -n "$GPTOKEYB2" ]; then
  $GPTOKEYB2 "ruffle_sdl" -c "$GAMEDIR/fancypants.gptk" &
else
  $GPTOKEYB "ruffle_sdl" -c "$GAMEDIR/fancypants.gptk" &
fi
pm_platform_helper "$GAMEDIR/ruffle_sdl"

# FPA_FPS_LOG=1 in fancypants.cfg writes the frame rate to log.txt
[ "$FPA_FPS_LOG" = "1" ] && FPS_ENV="RUFFLE_FPS_LOG=1 RUFFLE_SDL_TIMING=1"

port_log "starting the game, quality $FPA_QUALITY, aspect $FPA_ASPECT, world fps $FPA_WORLD_FPS"
# ruffle_sdl: Ruffle on the firmware's own SDL2 and GLES 3 (no Weston or X11 needed)
# run-ruffle restarts Ruffle when the game switches worlds, so only one world is in memory
env RUST_LOG=warn,ruffle_core::player::port_fps=info,ruffle_sdl=info $FPS_ENV \
  "$GAMEDIR/tools/run-ruffle" "$GAMEDIR/ruffle_sdl" --stage-scale movie --quality "$FPA_QUALITY" \
    -Paspect="$FPA_ASPECT" -Pworldfps="$FPA_WORLD_FPS" --save-directory "$GAMEDIR/saves" \
    "$DATADIR/ClassicPack-port.swf"

# Clean up after ourselves
port_exit
pm_finish
