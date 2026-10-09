# Testing

## On the device, through the EmulationStation API

Knulli (like Batocera) runs an HTTP API inside EmulationStation on `127.0.0.1:1234`. Calling it over SSH starts the port exactly as a player would: the same launcher, the same `emulatorlauncher` wrapper, gptokeyb, per game power mode and PortMaster patcher screen. Starting the launcher by hand from an SSH shell skips all of that and gives misleading results.

| Request | What it does |
|--|--|
| `curl http://127.0.0.1:1234/systems/ports/games` | JSON list of the Ports entries, with their `path`. Use it to check the launcher is known. |
| `curl http://127.0.0.1:1234/reloadgames` | Rescans the game lists (after copying a new launcher onto the device). |
| `curl -X POST -d '/userdata/roms/ports/Fancy Pants Adventures.sh' http://127.0.0.1:1234/launch` | Starts that entry. The body is the plain path, not JSON. |

Pitfalls found the hard way:

* `/launch` with a path ES does not list does not fail: it starts whichever game is selected in the menu. Always check `/systems/ports/games` first (`tests/device.sh launch` does).
* Paths with spaces: `scp` to such a path fails; copy with `ssh host "cat > '<path>'" < file` instead.
* `pkill -f pattern` or `pgrep -f pattern` run through `ssh host "..."` also match the remote shell whose command line contains the pattern, which kills your own SSH session (exit 255). A bracketed pattern such as `pgrep -f "[k]eyd.py"` only helps when the plain name appears nowhere else in that command line; a pid file or `pidof ruffle` is safer (`tests/device.sh keyd` uses a pid file).
* The first launch, and the first launch after a patch version bump, shows PortMaster's patcher screen, which waits for a button press when it finishes. Send `enter` through keyd to continue.
* Per game settings live in `/userdata/system/batocera.conf`, for example `ports["Fancy Pants Adventures.sh"].powermode=highperformance` (set it with `/usr/bin/knulli-settings-set`, or in the game's options in ES).

## tests/device.sh

A wrapper around the above for a Knulli device reachable by SSH. It reads `FPA_HOST` (default `knulli`), `FPA_PASS` (an `sshpass` password file, default `~/.ssh/knulli.pass`), `FPA_LAUNCHER` and `FPA_DIR` (the installed launcher and port folder).

```
tests/device.sh keyd                                  # start the virtual keyboard on the device
tests/device.sh launch                                # start the port through ES
tests/device.sh keys "enter 200" "sleep 3000" "s 200" # press keys
tests/device.sh shot title                            # screenshot to tests/out/title.png
tests/device.sh stat                                  # fps log, Ruffle memory, free memory
tests/device.sh stop
```

`tests/keyd.py` runs on the device: a uinput keyboard (`fpa-test-keys`) that reads lines like `right 2000` (hold for 2 s) or `sleep 500` from the FIFO `/tmp/fpa/keys`. It feeds the game keyboard keys directly, so it works with or without gptokeyb. The game's keys, as `fancypants.gptk` maps them:

| Pad | Key |
|--|--|
| D-pad | `up` `down` `left` `right` |
| A (jump) | `s` |
| B (attack) | `a` |
| X | `d` |
| Start | `space` |
| L1 (quality) | `q` |

`shot` reads `/dev/fb0` directly and assumes the RG35XX H's 640x480, double buffered, BGRA framebuffer; adjust it for other screens.

## Measuring speed

Add `export RUFFLE_FPS_LOG=1 RUST_LOG=warn,ruffle_core::player::port_fps=info` to `ports/fancypants/fancypants.cfg` (the launcher sources it). Ruffle then writes a `port_fps` line to `log.txt` every two seconds (frame rate and where the frame time went). `tests/device.sh waitfps <n>` waits for `n` such lines and prints the last three. Remove the line afterwards.

Sampling the Ruffle main thread with `gdb -p $(pidof ruffle_sdl) -batch -ex 'thread 1' -ex bt` in a loop and symbolising the addresses against the unstripped aarch64 build (`work/ruffle-src/target/aarch64-unknown-linux-gnu/release/ruffle_sdl`, offset by the mapping base from `/proc/<pid>/maps`) gives a CPU profile; that is how the numbers in [PERFORMANCE.md](PERFORMANCE.md) were found. For ActionScript time, run with `RUFFLE_AS3_PROF=1` and `RUST_LOG=ruffle_core::avm2::function::as3prof=info` (patch 0003).

## On a PC

`tests/pc_run.sh <ruffle> <port dir> <seconds> <out prefix> [steps...]` runs an x86_64 Ruffle build (with the port's patches) against a prepared copy of the port on a private Xvfb display at 640x480 (`XRES` changes it), then runs the steps: `shot`, `sleep:<s>`, or any `xdotool` command such as `key s`. Screenshots and the log go next to the prefix. This is good for checking patches and layout quickly, but not for speed: a desktop GPU and CPU say nothing about the handheld.

Build the PC Ruffle from `work/ruffle-src` with `CARGO_TARGET_DIR=../target-x86 cargo build --release -p ruffle_desktop`, run from inside `work/ruffle-src`. Running cargo from another directory silently builds into a different target folder, and you end up testing a stale binary.

### The handheld front end (ruffle_sdl) on a PC

`tests/pc_sdl_run.sh <ruffle_sdl> <port dir> <WxH> <game> <level> <seconds> <out prefix> [steps...]` runs the same ruffle_sdl the port ships, built for x86_64, straight into a world and level (for example `World3 Level1`), at any screen size. Steps are `shot`, `s:<seconds>` and `tap:<SDL key name>` (Start is `space`). Screen grabs of an Xvfb or gamescope display only show black for its GL output, so the build carries a test only capture and key hook: apply `tests/sdl_test_hooks.py <ruffle source dir>` before building and `git checkout -- sdl/src/main.rs` after, so the hook never reaches the release binary.

The capture reads the window with `glReadPixels` on the GL context wgpu shares, and has to reset wgpu's pixel pack state for that read and restore it afterwards. In World 3 levels whose backgrounds go through `BitmapData.colorTransform` (Levels 1, 8, 9 and 10, for example), wgpu reads textures back through a pack buffer and leaves it bound with its own row length. With the buffer still bound every capture of those levels came out all black, although the game drew them correctly; with only the buffer unbound, the leftover row length made the read write past its buffer and crash.
