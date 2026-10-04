# Fancy Pants Adventures: Classic Pack for PortMaster

A [PortMaster](https://portmaster.games/) port of [The Fancy Pants Adventures: Classic Pack](https://store.steampowered.com/app/1668460/) (Brad Borne / Borne Games), the original Flash platformers (World 1, World 2, World 3 and the World 4 hub), for Linux handhelds.

The port runs the game's own SWF files in [Ruffle](https://ruffle.rs), a Flash Player emulator, with a few patches to Ruffle. No game files are included: you supply them from your Steam copy, and the first start patches them on your device with xdelta3.

| | |
|--|--|
| Status | Playable from start to finish on an RG35XX H (Knulli). Other devices and CFWs not yet tried. |
| Target | aarch64 PortMaster devices (Knulli, muOS, ROCKNIX and others) with 1 GB RAM or more |
| Runtimes | Westonpack (`weston_pkg_0.2`), bundled Ruffle build |
| Tested game version | current Steam release (MD5 sums in [port/fancypants/README.md](port/fancypants/README.md)) |
| Speed on an RG35XX H | Worlds 1 to 3: a steady 30 fps (their native rate). World 4 hub: about 15 fps (17 with Knulli's High performance mode), at the right game speed |

## For players

1. Buy the game on Steam.
2. Copy everything from its install folder into `ports/fancypants/gamedata/` on your device (you should see `ClassicPack.swf` and the folders `World1` to `World4`).
3. Start **Fancy Pants Adventures** from the Ports menu. The first start checks and patches the files and converts the World 4 textures, which takes a few minutes. Later starts are quick.

Controls, settings, notes and known limitations are in [port/fancypants/README.md](port/fancypants/README.md), the file that ships with the port.

## How it works

```
Fancy Pants Adventures.sh (PortMaster launcher)
  ├ first start, or after a port update: tools/patchscript   (PortMaster patcher screen)
  │   ├ checks MD5 sums, inflates each SWF and applies tools/patch/*.xdelta (originals kept as *.orig)
  │   └ tools/fpa-prep converts World 4's ATF textures to half resolution PNGs
  └ westonwrap.sh ... crusty_x11egl                            (Weston + Xwayland, GLES)
      └ tools/run-ruffle.sh ruffle ... ClassicPack-port.swf
          └ restarts Ruffle straight into the next world whenever the game switches worlds
```

The Classic Pack is an Adobe AIR app: an ActionScript 3 shell (`ClassicPack.swf`) that loads the three ActionScript 2 games and the World 4 hub, which is ActionScript 3 on Starling and Stage3D. The port changes:

* **The shell** (`patch/patch_shell.py`): Steamworks, AIR windowing and file APIs and GameInput are removed, settings and progress go to a local SharedObject, quitting uses `fscommand`, and switching worlds asks the launcher to restart Ruffle (one world in memory at a time). It also sets the frame rate and draws a backdrop for screens that are not 3:2.
* **Worlds 1 to 3** (`patch/patch_world_as2.py`, applied to P-code): the camera can grow taller on 4:3 screens and small rooms stay centered. World 2 advances its clock by the real frame time and caches its levels at 1x instead of 1.5x resolution, so it keeps its speed at 30 fps and fits in 1 GB.
* **World 4** (`patch/patch_world4.py`): textures load from PNG files instead of ATF, atlases are scaled to match, and Starling's texture uploads go through `BitmapData.draw`.
* **Ruffle** (`build/ruffle-patches/`): an implementation of `Graphics.readGraphicsData` (World 4 builds its collision with it), Stage3D draw batching with pipeline and bind group caches, GPU side texture uploads, the relaunch command and an optional frame rate log.
* **`fpa-prep`** (`tools/fpa-prep/`): a small Rust tool that decodes Adobe's ATF textures (JPEG XR endpoints plus LZMA compressed DXT indices) to PNG, scales World 4's atlas XML files and inflates SWFs on the device.

The patch scripts work on source that JPEXS decompiles from your own SWF files at build time, so no game code is stored here. Measurements, what helped, and every approach that failed are in [docs/PORTING.md](docs/PORTING.md) and [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

## Repository layout

| Path | Contents |
|--|--|
| `port/` | Exactly what ships to `ports/` on the device (plus the `ruffle` and `fpa-prep` binaries after building) |
| `patch/` | Game patch scripts: decompile with JPEXS, patch the scripts, put them back |
| `build/` | Ruffle fetch and cross build, the Ruffle patches, `fpa-prep` cross build, `make_patches.sh`, `package.sh`, and a failed threading experiment kept for reference |
| `tools/fpa-prep/` | Source of the texture converter |
| `tests/` | Device testing through the EmulationStation API (`device.sh`, `keyd.py`) and a PC runner (`pc_run.sh`) |
| `docs/` | Porting, performance and testing notes |

## Building

Requirements: Docker, Java (for [JPEXS ffdec](https://github.com/jindrapetrik/jpexs-decompiler), tested with 26.3.0), Python 3, git, zip, and your copy of the game.

```
build/fetch_ruffle.sh work/ruffle-src                     # Ruffle 0.7.0 nightly 2026.10.4 with the port's patches
build/build_ruffle.sh work/ruffle-src work/ruffle-arm      # aarch64 Ruffle (Ubuntu 20.04 image, glibc 2.30 symbols)
cp work/ruffle-arm/ruffle port/fancypants/
build/build_prep.sh port/fancypants/tools                  # aarch64 fpa-prep
FFDEC=/path/to/ffdec.jar build/make_patches.sh /path/to/Classic\ Pack   # the xdelta3 patches
build/package.sh                                           # fancypants.zip, ready to unzip into ports/
```

`make_patches.sh` rebuilds the shipped patches byte for byte from the Steam files. When a patch changes, raise the number in `port/fancypants/tools/patch/version` so prepared installs patch again on their next start.

## Testing

On the device, the port is started through EmulationStation's HTTP API over SSH, so it runs exactly as a player starts it, and driven by a small uinput keyboard:

```
tests/device.sh keyd && tests/device.sh launch
tests/device.sh keys "enter 200" "sleep 3000" "right 2000" && tests/device.sh shot hub
```

The API calls, their pitfalls, frame rate logging, profiling and the PC runner are described in [docs/TESTING.md](docs/TESTING.md).

## Known limitations

* World 4 (the hub) is CPU bound at about 15 fps on a Cortex A53 at 1.5 GHz. It is timed by the clock, so it plays at the right speed. Moving GPU work to a second thread does not work with the Mali blob driver under Westonpack (see docs/PERFORMANCE.md).
* Entering a world door shows a short black screen while Ruffle restarts.
* Steam achievements and Steam Cloud saves are not available; progress is saved locally.
* Only the current Steam release is supported (the patcher checks MD5 sums).

## Credits and licenses

* The Fancy Pants Adventures by Brad Borne / Borne Games. Not affiliated; buy the game to play it.
* [Ruffle](https://ruffle.rs) (MIT or Apache 2.0). The bundled build is patched as described above.
* [Westonpack](https://github.com/binarycounter/Westonpack) by binarycounter, the PortMaster team.
* Adobe's open source [dds2atf](https://github.com/adobe/dds2atf), which documents the ATF format.
* [JPEXS Free Flash Decompiler](https://github.com/jindrapetrik/jpexs-decompiler), used at build time.
* Everything written for this port (launcher, patch scripts, fpa-prep, build scripts, docs) is MIT licensed, see [LICENSE](LICENSE).
