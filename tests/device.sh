#!/bin/bash
# device.sh: drive the installed port on a Knulli (Batocera based) device over SSH,
# launching it through EmulationStation's HTTP API like a player would.
#   device.sh launch              start the port through ES (POST /launch)
#   device.sh stop                stop Ruffle (returns to ES)
#   device.sh keyd                copy tests/keyd.py to the device and start it
#   device.sh keys "right 2000" "a 200" "sleep 500" ...   press keys through keyd
#   device.sh shot <name>         framebuffer to tests/out/<name>.png (assumes a 640x480
#                                 double buffered BGRA fb0, as on the RG35XX H)
#   device.sh stat                last fps log lines, Ruffle RSS, free memory
#   device.sh waitfps <n>         wait for n port_fps lines in log.txt, print the last 3
# Settings (environment): FPA_HOST (ssh host, default knulli), FPA_PASS (sshpass password
# file, default ~/.ssh/knulli.pass), FPA_LAUNCHER, FPA_DIR.
here=$(cd "$(dirname "$0")" && pwd)
HOST=${FPA_HOST:-knulli}
PASS=${FPA_PASS:-$HOME/.ssh/knulli.pass}
LAUNCHER=${FPA_LAUNCHER:-/userdata/roms/ports/Fancy Pants Adventures.sh}
DIR=${FPA_DIR:-/userdata/roms/ports/fancypants}
OUT=$here/out; mkdir -p "$OUT"
S() { sshpass -f "$PASS" ssh -o ConnectTimeout=10 "$HOST" "$@"; }
LOG="sed 's/\x1b\[[0-9;]*m//g' '$DIR/log.txt'"
case $1 in
  launch)
    # ES only launches paths it has in its game list; an unknown path starts the
    # currently selected game instead, so check first.
    S "curl -s -m 5 http://127.0.0.1:1234/systems/ports/games | grep -qF '$LAUNCHER'" \
      || { echo "ES does not list $LAUNCHER (try: curl http://127.0.0.1:1234/reloadgames)"; exit 1; }
    S "curl -s -m 5 -X POST -d '$LAUNCHER' http://127.0.0.1:1234/launch";;
  stop) S 'kill $(pidof ruffle) 2>/dev/null; sleep 4; pidof ruffle || echo stopped';;
  keyd) S 'mkdir -p /tmp/fpa && cat > /tmp/fpa/keyd.py' < "$here/keyd.py"
        S 'pgrep -f "[k]eyd.py" >/dev/null || (setsid nohup python3 /tmp/fpa/keyd.py >/tmp/fpa/keyd.log 2>&1 </dev/null &)';;
  keys) shift; printf '%s\n' "$@" | S 'cat > /tmp/fpa/keys';;
  shot) S 'mkdir -p /tmp/fpa && cd /tmp/fpa && dd if=/dev/fb0 of=fb.raw bs=2560 count=960 2>/dev/null && ffmpeg -loglevel error -y -f rawvideo -pix_fmt bgra -s 640x960 -i fb.raw -vf crop=640:480:0:$(cut -d, -f2 /sys/class/graphics/fb0/pan) s.png && cat s.png' > "$OUT/$2.png" && echo "$OUT/$2.png";;
  stat) S "$LOG | grep -E 'port_fps|panic|ERROR [^r]' | tail -3; P=\$(pidof ruffle); [ -n \"\$P\" ] && grep VmRSS /proc/\$P/status; free -m | sed -n 2p";;
  waitfps)
    until [ "$(S "grep -c port_fps '$DIR/log.txt'")" -ge "$2" ] 2>/dev/null; do sleep 5; done
    S "$LOG | grep port_fps | tail -3 | sed 's/.*port_fps: //'";;
  *) sed -n '2,13p' "$0"; exit 1;;
esac
