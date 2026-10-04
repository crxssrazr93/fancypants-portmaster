#!/bin/bash
# run-ruffle.sh <ruffle> <args...> <file.swf>
# Runs Ruffle. When the game switches to another world it prints "FPA_RELAUNCH <game> <level> <door>"
# and exits; Ruffle is then started again straight into that world, so every world gets all of
# the handheld's memory instead of piling up next to the previous one.
# Only bash builtins read Ruffle's output: Westonpack preloads a library into every process that
# prints its own banner, so external filters (sed, tail) would add lines of their own.
ruffle=$1
shift
swf=${!#}
set -- "${@:1:$#-1}"
next=()
while :; do
  target=""
  while IFS= read -r line; do
    printf '%s\n' "$line" >&2
    case $line in
      "FPA_RELAUNCH "*) target=${line#FPA_RELAUNCH } ;;
    esac
  done < <("$ruffle" "$@" "${next[@]}" "$swf" 2>&1)
  [ -n "$target" ] || break
  read -r game level door <<< "$target"
  echo "=== switching to $game $level (door $door) ===" >&2
  next=(-Pgame="$game" -Plevel="$level" -Pdoor="$door")
done
