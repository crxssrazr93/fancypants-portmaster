## Installation

Buy the game on [Steam](https://store.steampowered.com/app/1668460/) and copy everything from its install folder into `ports/fancypants/gamedata/` (you should see `ClassicPack.swf` and the folders `World1` to `World4`). The first launch patches the files and converts the World 4 textures, which takes a few minutes. Only the current Steam release is supported.

## Controls

| Button | Action |
|--|--|
| D-pad / Left stick | Move, Up enters doors, Down ducks |
| A / B / X / Y | Jump / Attack / Special / Special 2 |
| Start | Pause |
| L1 / L2 | Cycle quality / Mute music |
| Right stick, R1 / R2 | Mouse, click |
| Select + Start | Quit |

## Notes

* World 4 (the hub) runs at about 15 fps on an RG35XX H, but at the right game speed.
* World 3 is the heaviest world. On an RG35XX H it keeps close to full speed by drawing fewer frames when busy, so it can look choppier than Worlds 1 and 2.
* Entering a world door shows a short black screen while Ruffle restarts to free memory.
* Steam achievements and cloud saves are not available, progress is saved locally.
* Settings (quality, screen fit, frame rate) are in `ports/fancypants/fancypants.cfg`.

## Thanks

Brad Borne / Borne Games for the game, the [Ruffle](https://ruffle.rs) team, BinaryCounter for [Westonpack](https://github.com/binarycounter/Westonpack), and Adobe for dds2atf.

Source and build details: https://github.com/crxssrazr93/fancypants-portmaster
