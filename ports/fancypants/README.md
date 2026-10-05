## Notes

Fancy Pants Adventures: Classic Pack running in [Ruffle](https://ruffle.rs) (a Flash Player emulator written in Rust) through the Westonpack runtime.

Thanks to Brad Borne / Borne Games for the game, the Ruffle team for the emulator, BinaryCounter for Westonpack, and Adobe for open sourcing dds2atf (which documents the ATF texture format).

## Installation

1. Buy the game on [Steam](https://store.steampowered.com/app/1668460/).
2. Copy everything from its install folder into `ports/fancypants/gamedata/` (you should see `ClassicPack.swf` and the folders `World1` to `World4`). Without a Windows PC you can download the files with the [Steam console](https://steamcommunity.com/sharedfiles/filedetails/?id=873543244): `download_depot 1668460 1668461 7660244324469957005`
3. Launch the port. The first launch checks the files, patches them and converts the World 4 textures. This takes a few minutes and only happens once. A log is written to `ports/fancypants/patchlog.txt`.

Only the current Steam release is supported. The patcher checks MD5 sums:

| File | MD5 |
|--|--|
| ClassicPack.swf | 499ece31db0c8158f1749b51a87f318c |
| World1/FPAWorld1.swf | ed23ca34bb477fda2c63683004301709 |
| World2/FPAWorld2.swf | 11288816abe8507da4afb25252939e30 |
| World3/FPAWorld3.swf | a7e6976dbe405908482e162d910d7f5e |
| World4/FPAWorld4.swf | 668885cc8a645f3e56ba21821369f4d8 |

The original files are kept next to the patched ones as `*.orig`. When the port is updated with new patches, they are applied again on the next launch.

## What the port changes

Nothing is redistributed. Your files are patched on the device with xdelta3:

* The Classic Pack launcher no longer needs Steam or Adobe AIR: its Steamworks calls (achievements and Steam Cloud) are removed, which the game does not need to run. This is not a DRM bypass; the game has no DRM and you need your own copy. Settings and progress are saved locally (in `ports/fancypants/saves`).
* Worlds 1 and 2 run at a steady 30 fps on handhelds (see `FPA_WORLD_FPS`). World 2 advances its game clock by the real frame time, so it keeps its speed at 30 fps, and caches its levels at 1x instead of 1.5x resolution so they fit in 1 GB of RAM.
* Worlds 1 to 3 support screens narrower than 3:2. The games already widened their camera for wide screens; the patch lets the camera grow taller on 4:3 screens too, and keeps small rooms centered.
* World 4 (the hub) loads its textures as PNG files. Adobe's lossy ATF textures can't be decoded by Ruffle and the handheld GPUs can't sample DXT textures, so they are converted at half resolution by `tools/fpa-prep` on first launch.
* Moving between worlds restarts Ruffle instead of keeping every world in memory. The original launcher keeps each world loaded in the background, which does not fit in 1 GB of RAM. You will see a short black screen when you enter a world door.
* The bundled Ruffle build includes an implementation of `Graphics.readGraphicsData`, which World 4 uses to build its collision (without it Fancy Pants falls through the floor). It also batches and caches Stage3D work and keeps World 4's textures on the GPU, which makes the hub several times faster on handheld CPUs.

## Controls

| Button | Action |
|--|--|
| D-pad / Left stick | Move, Up enters doors, Down ducks |
| A | Jump |
| B | Attack |
| X | Special |
| Y | Special 2 |
| Start | Pause |
| L1 | Cycle quality (World 1 to 3) |
| L2 | Mute music |
| Right stick | Mouse |
| R1 / R2 | Mouse click |
| Select + Start | Quit |

## Settings

`ports/fancypants/fancypants.cfg` (reinstalling or updating the port resets it to the defaults):

* `FPA_QUALITY`: `low` (default, fastest), `medium` or `high`.
* `FPA_ASPECT` (how the 3:2 Worlds 1 to 3 use the screen; World 4 always adapts by itself):
  * `extend` (default): fills the whole screen. On 4:3 the game shows a little more of the level above and below.
  * `fit`: the original 3:2 view, centered with black bars at the top and bottom.
  * `fill`: fills the screen with the 3:2 view and trims the sides, which cuts off the HUD on 4:3 screens.
* `FPA_WORLD_FPS`: `30` (default) or `60`, the frame rate of Worlds 1 and 2. Their game logic runs at 30 ticks per second either way. At 60 fps the motion is smoother, but a device that can't hold 60 fps makes the game speed uneven.
* `FPA_GL_LIBRARY`: the Westonpack GL mode, `crusty_x11egl` by default. If you only get a black screen (for example on ROCKNIX with panfrost), try `system`.

## Known issues

* Tested on an RG35XX H (Knulli). Other devices and CFWs use the same files but have not all been tried.
* With `FPA_ASPECT="extend"` on 4:3 screens, some rooms in World 1 show an empty white strip below the bottom of the level, where the original 3:2 view ended. `fit` avoids it, with black bars instead.
* World 4 (the hub) is the heaviest part because it uses Stage3D, and the CPU is the limit (lowering the resolution does not help). On an RG35XX H it runs at about 15 fps. Its game logic is timed by the clock, so it plays at the right speed, just less smoothly.
* For a little more speed in the hub on Knulli, set the game's power mode to "High performance" (game options in EmulationStation). This raised the hub from about 15 to 17 fps on an RG35XX H.
* Worlds 1 to 3 run at 30 fps, the frame rate of the original Flash games. Keep `FPA_QUALITY="low"` (the default) for the best speed.
* `FPA_FPS_LOG="1"` in `fancypants.cfg` writes the frame rate to `log.txt`, which helps when reporting performance.

## Compile

Source, build scripts and porting notes: https://github.com/crxssrazr93/fancypants-portmaster

* `ruffle` is Ruffle 0.7.0 nightly 2026.10.4 with the port's patches (`build/ruffle-patches/`), cross built for aarch64 with `build/fetch_ruffle.sh` and `build/build_ruffle.sh`.
* `tools/fpa-prep` (the texture converter) is built with `build/build_prep.sh`.
* The xdelta3 patches are made from the Steam files with `build/make_patches.sh`.
