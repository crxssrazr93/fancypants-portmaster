# Performance notes (RG35XX H, H700, Mali G31, Knulli)

Measured with `RUFFLE_FPS_LOG=1` (frame rate and timings in `log.txt`, see [TESTING.md](TESTING.md)) and, for AS3, `RUFFLE_AS3_PROF=1` with `RUST_LOG=ruffle_core::avm2::function::as3prof=info`.

## Where the time goes

Worlds 1 to 3 (AS2, software shapes): about 10 to 22 ms per frame, so a steady 30 fps.

World 4 (the hub, Starling on Stage3D) is CPU bound on a single A53 core, about 60 ms per frame:

| Part | Time per frame |
|--|--|
| ActionScript (game logic and Starling) | about 25 ms |
| wgpu encoding about 36 Stage3D draws (one render pass each) at `finish()` | about 13 ms |
| Mali GL driver executing them (replayed at `queue.submit`) | about 13 ms |
| `hitTestPoint` (about 870 calls) | 3 to 6 ms |

Shrinking the Stage3D back buffer to a quarter of its pixels did not change the frame rate at all, so the GPU fill rate is not a factor.

## What helped

* Batching Stage3D draws into one command encoder per frame, a pipeline cache and a bind group cache (2.9 to 15 fps).
* Starling's per frame texture uploads: `BitmapData.draw` instead of `copyPixels`, plus copying GPU side bitmaps straight into Stage3D textures. The renderer must submit its pending offscreen draws first (`flush_pending_gpu_work`), or the copy reads an empty texture (invisible character).
* Worlds 1 and 2 locked to 30 fps. Their game clock is 30 Hz; between 30 and 60 fps World 1's speed jumped between about 0.65x and 1.3x, and World 2 ran in slow motion.
* World 2 caching levels at `bitRes = 1` instead of 1.5 (it ran out of memory in Level 1).
* Knulli's "High performance" power mode (performance governor): 15.3 to 16.6 fps in the hub. Allowing 1.704 GHz instead of the 1.512 GHz cap gave 18.2 fps, but the port does not change clocks.

## What did not help (do not retry without a new idea)

* LTO for the Ruffle build: no measurable gain, much longer builds.
* Capping `BitmapData.drawWithQuality` at the stage quality (no MSAA offscreen): slower (13.7 instead of 15.5 fps). Mali handles MSAA cheaply.
* Lower Stage3D resolution: no gain (see above).
* Moving GPU submission to a second thread (`build/experiments/gpu-thread-attempt.diff` and `gpu_worker.rs`). It worked on desktop Mesa (main thread time halved) but not on the Mali blob driver (tested under Westonpack and crusty):
  * `glClientWaitSync` returns 0 instead of a status, so any real fence wait fails (wgpu reports `GpuWaitTimeout` on `Surface::configure`). `GlFenceBehavior::AutoFinish` avoids the waits.
  * Creating the window surface renderbuffer on the second thread fails.
  * With submission and presentation on the second thread, buffers created on the main thread at the same time come out invalid (seen in shape vertex buffers), even though wgpu-hal serialises GL access with its context mutex.
  * The single threaded `queue.submit`, `present` and `configure` path is the only reliable one on this stack.

## World 3

World 3 (AS2) advances one fixed step per frame at 30 fps and has no clock correction, so any frame over 33 ms slows the game itself down. Measured on an RG35XX H in Level 4 (game frames per second; the original Classic Pack also runs World 3 at 30):

| | Standing | Jumping | Running |
|--|--|--|--|
| Before | 15 | 12 to 13 | 8 to 13 |
| Lazy mouse picking and frame skip | 28 to 29 | 22 to 23 | 23 to 30 |

* Ruffle searched for the clip under the mouse on every frame, walking every clip of the level and looking up button handlers on each. That was about 35% of the main thread. `RUFFLE_LAZY_MOUSE_PICK` (patch 0004, set by `tools/run-ruffle` for Worlds 1 to 3) only searches again when the mouse moves or clicks.
* Ruffle stops catching up once game logic takes more than a third of a frame, so slow frames were simply lost. `RUFFLE_FRAMESKIP` (patch 0004, World 3 only) allows two game frames per screen update when behind. The picture then updates 12 to 19 times per second when busy.
* Level 4 cached its level art at 1.5x and Ruffle was killed for running out of memory while loading it; it now caches at 1x like the other levels (patch version 8). Under Westonpack, memory still peaked at 700 to 790 MB while a World 3 level loaded, and Level 1 was killed once at 1x (see "Memory with ruffle_sdl" below for the current figures).
* Caching at 0.5x instead of 1x saved about 75 MB and 3 fps standing still, but made the level art visibly blockier; not used.
* Remaining cost in Level 4: the game's own scripts, garbage collection and drawing, each 15 to 20%.

## Memory with ruffle_sdl

Patches 0005 to 0011 (pull request #1) replaced Ruffle desktop on Westonpack with `ruffle_sdl` and changed how Ruffle holds a world in memory. Same RG35XX H, same game files, measured the same way (Ruffle RSS and Mali GPU memory, peaks):

| | Before (Westonpack) | ruffle_sdl |
|--|--|--|
| World 1 Level 1 | | 30 fps, 204 MB plus 109 MB GPU |
| World 2 Level 1 | 30 fps, 771 MB plus 503 MB GPU, 117 MB in zram | 30 fps, 222 MB plus 85 MB GPU, no swap used, flat while moving |
| World 3 Level 4, no swap | 24 game and 12 drawn fps, killed for lack of memory | 30 game and 20 drawn fps, 296 MB plus 135 MB GPU |
| World 4 hub | about 15 fps | about 16 fps, 250 MB |

Memory now grows as a level is explored. In a longer World 3 session (bedroom menu, then the rooftop level) it held at 666 to 700 MB and peaked at 803 MB plus 450 MB GPU, with about 300 MB in zram, so zram is still recommended on 1 GB devices.

Each change has a switch that restores the old path: `RUFFLE_LAZY_SHAPES=0`, `RUFFLE_LAZY_SHAPE_RECORDS=0`, `RUFFLE_DRAW_IN_PLACE=0`, `RUFFLE_DRAW_POOL_MB=0`, `RUFFLE_ZEROED_PIXELS=0`, `RUFFLE_EMPTY_TEXTURES=0`, `RUFFLE_S3D_DEFER_UPLOAD=0`, `RUFFLE_S3D_MERGE_PASSES=0`. `RUFFLE_MEMLOG=1` logs memory by category.

## Ideas not tried yet

* Coalescing `SetProgramConstants` uploads per draw.
