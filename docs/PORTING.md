# Porting notes

How the Classic Pack was brought to 1 GB ARM handhelds, in the order the problems came up. Performance measurements and the failed threading experiment are in [PERFORMANCE.md](PERFORMANCE.md).

Test device: Anbernic RG35XX H (Allwinner H700, four Cortex A53 cores at up to 1.5 GHz under the default governor, Mali G31 with the blob driver, 1 GB RAM, 640x480), Knulli, Westonpack in `crusty_x11egl` mode.

## 1. Why Ruffle

The Steam release is an Adobe AIR app with SWF content, and there is no AIR runtime for ARM Linux. Ruffle runs SWFs natively, handles ActionScript 2 well and ActionScript 3 well enough, and has a wgpu renderer that can use GLES through Westonpack. Its desktop build only needed slimming for handhelds (rustls instead of OpenSSL, no fontconfig, no OpenH264 download, tuned for Cortex A53).

## 2. The shell

`ClassicPack.swf` (class `SuperLoaderMain`) depends on the Steamworks AIR native extension, `NativeApplication`, `NativeWindow`, `File` and GameInput. `patch/patch_shell.py` edits the JPEXS decompiled source with anchored replacements (each anchor must match an exact number of times, so a different game version fails loudly instead of patching the wrong place):

* Steam and AIR calls removed; settings and progress stored in a local SharedObject (Ruffle saves it under `ports/fancypants/saves`).
* Quit through `fscommand("quit")`.
* Boot parameters (`-P` flashvars from the launcher) choose the world, level and door to start in, the aspect mode and the frame rate.
* Screen aspect: Worlds 1 to 3 are 3:2. `extend` (the default) passes the real screen size to the games, `fit` keeps 3:2 with black bars, `fill` crops the sides.
* The stage behind the games is white, like the original. A black backdrop made the black stick figure invisible wherever a level has no background.

## 3. Memory: one world at a time

The original shell keeps every world it has loaded resident and preloads the next ones. On 1 GB that runs out of memory after a world or two. The shell now prints `FPA_RELAUNCH <game> <level> <door>` and exits Ruffle when the player enters a door; `tools/run-ruffle.sh` starts Ruffle again straight into that world. A short black screen is the cost.

`run-ruffle.sh` only uses bash builtins to read Ruffle's output, because Westonpack preloads a library into every process that prints its own banner, so `sed` or `tail` in the pipe would add lines of their own.

World 2 also ran out of memory inside Level 1 on its own: it renders each level into cached bitmaps at 1.5x the 720x480 base resolution. Caching at 1x fixed it, and a 480p screen cannot show the difference.

## 4. World 4 textures

The hub uses Starling on Stage3D with Adobe ATF textures. Most are lossy ATF (DXT data whose endpoint colours are stored as a JPEG XR image and whose index bits are LZMA compressed), which Ruffle cannot decode, and the Mali G31 cannot sample DXT anyway. `fpa-prep` decodes them on the device at first start (format notes are in the header of `tools/fpa-prep/src/main.rs`, worked out from Adobe's `dds2atf` source) and writes PNGs at half resolution. `patch/patch_world4.py` makes the game load those PNGs by URL and scales the atlas coordinates to match: the embedded atlas inside the AS3 code and the level atlases on disk (missing this made doors and effects appear at the wrong size in Levels 2 and 3).

JPEXS recompiles some decompiled AS3 slightly wrong, so the World 4 patch only replaces the three classes it changes.

## 5. Collision in World 4

Fancy Pants fell through the floor of the hub. World 4 builds its collision shapes with `Graphics.readGraphicsData`, which Ruffle did not implement. `build/ruffle-patches/0001` adds it.

## 6. Patch delivery

Patches are xdelta3 files against the inflated (uncompressed) SWFs: a delta against a zlib compressed SWF is as big as the file, against the inflated one it is a few KB. The device inflates its originals with `fpa-prep inflate` before applying them.

* PortMaster's `xdelta3` has no LZMA secondary compressor, so deltas are made with `-S none` (the default build fails on the device with "unavailable secondary compressor: LZMA").
* The patcher keeps the originals as `*.orig` and stamps the prepared install with `tools/patch/version`. When a port update ships new patches with a higher number, the next start patches again from the originals.
* World 3 loads `OtherStuff/...` relative to the root movie in Ruffle (AIR resolved it next to `FPAWorld3.swf`), so the patcher moves that folder to the game root.

## 7. Frame rate and game speed

The worlds were written for a 30 Hz game clock:

* World 1 advances by half a tick when a frame took under 25 ms and a whole tick otherwise. A handheld that hovers around 60 fps keeps crossing that threshold, and the game speed jumped between about 0.65x and 1.3x.
* World 2 always advanced by half a tick, assuming 60 fps, so below 60 fps it ran in slow motion. The patch gives it World 1's rule.
* World 3 already ran its frames at 30 fps.

The shell sets 30 fps for Worlds 1 to 3 (`FPA_WORLD_FPS="60"` restores 60 for Worlds 1 and 2), which the RG35XX H holds steadily.

World 4 is timed by the clock (its step is the elapsed time divided by 33 ms), so it plays at the right speed at any frame rate. On the RG35XX H it reaches about 15 fps, see [PERFORMANCE.md](PERFORMANCE.md) for where the time goes.

## 8. Launcher

* gptokeyb2 on muOS, gptokeyb elsewhere, mapping the pad to Flash's keyboard controls with the right stick as the mouse.
* The real `XDG_RUNTIME_DIR` is passed through so audio works inside Westonpack.
* ROCKNIX gets the crusty preload; `FPA_GL_LIBRARY="system"` is the escape hatch for drivers where crusty gives a black screen.
* Knulli's per game "High performance" power mode raises the hub from about 15 to 17 fps. The port does not change CPU clocks itself.
