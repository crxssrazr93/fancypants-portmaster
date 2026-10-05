#!/usr/bin/env python3
# keyd.py: runs ON THE DEVICE. A virtual keyboard fed from a FIFO (/tmp/fpa/keys).
# Each line: "<KEY> <ms>" (hold the key that long) or "sleep <ms>".
# Needs python-evdev and /dev/uinput (both present on Knulli).
import os, time
from evdev import UInput, ecodes as e

keys = {k: getattr(e, "KEY_" + k.upper()) for k in
        ["up", "down", "left", "right", "s", "a", "d", "space", "enter", "esc", "q", "m"]}
ui = UInput({e.EV_KEY: list(keys.values())}, name="fpa-test-keys")
fifo = "/tmp/fpa/keys"
os.makedirs("/tmp/fpa", exist_ok=True)
with open("/tmp/fpa/keyd.pid", "w") as f:
    f.write(str(os.getpid()))
if not os.path.exists(fifo):
    os.mkfifo(fifo)
while True:
    with open(fifo) as f:
        for line in f:
            p = line.split()
            if len(p) != 2:
                continue
            if p[0] == "sleep":
                time.sleep(int(p[1]) / 1000)
                continue
            k = keys[p[0].lower()]
            ui.write(e.EV_KEY, k, 1); ui.syn(); time.sleep(int(p[1]) / 1000)
            ui.write(e.EV_KEY, k, 0); ui.syn()
