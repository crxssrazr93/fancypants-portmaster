#!/usr/bin/env python3
"""Let the AS2 worlds (FPAWorld1-3) use a screen narrower than 3:2 (4:3 handhelds).

The worlds already support wider screens: SetDimensions() derives scaledStageWidth/Height from the
aspect the shell reports. For narrower screens it computes the taller height but
 * only widens the camera clip (ScrollRect), so the bottom of the view stayed blank, and
 * World 3's setBounds() only centres rooms narrower than the view, so in rooms shorter than the
   view the vertical camera clamp flipped between top and bottom every few frames.
World 2's game clock also gets a frame time based step (see W2_TICK_NEW).
Usage: patch_world_as2.py <exported pcode dir> <out dir>
Prints "<script name>\t<patched file>" for each script to replace.
"""
import os
import sys

exp, out = sys.argv[1], sys.argv[2]

SCROLLRECT = """Push "ScrollRect"
GetVariable
Push "width", "scaledStageWidth"
GetVariable
Push 10
Add2
SetMember
"""

# World 3 setBounds(): centre short rooms vertically, mirroring what it does horizontally
W3_BOUNDS_OLD = """Push "stageX"
GetVariable
Less2
Not
If {end}
Push "MaxX"
GetVariable
Push "MinX"
GetVariable
Add2
Push 2
Divide
StoreRegister 1
Pop
Push "MaxX", register1, "scaledStageWidthHalf"
GetVariable
Add2
SetVariable
Push "MinX", register1, "scaledStageWidthHalf"
GetVariable
Subtract
SetVariable
}}
{end}:"""
W3_BOUNDS_NEW = """Push "stageX"
GetVariable
Less2
Not
If locporty
Push "MaxX"
GetVariable
Push "MinX"
GetVariable
Add2
Push 2
Divide
StoreRegister 1
Pop
Push "MaxX", register1, "scaledStageWidthHalf"
GetVariable
Add2
SetVariable
Push "MinX", register1, "scaledStageWidthHalf"
GetVariable
Subtract
SetVariable
locporty:Push "MaxY"
GetVariable
Push "MinY"
GetVariable
Subtract
Push "stageY"
GetVariable
Less2
Not
If {end}
Push "MaxY"
GetVariable
Push "MinY"
GetVariable
Add2
Push 2
Divide
StoreRegister 1
Pop
Push "MaxY", register1, "scaledStageHeightHalf"
GetVariable
Add2
SetVariable
Push "MinY", register1, "scaledStageHeightHalf"
GetVariable
Subtract
SetVariable
}}
{end}:"""

# World 2 always advanced its 30 Hz game clock by half a tick per frame (it assumed 60 fps), so
# below 60 fps it ran in slow motion. Use a whole tick on slow frames, like Worlds 1 and 3 do;
# the port runs Worlds 1 and 2 at a steady 30 fps on handhelds.
W2_TICK_OLD = """DefineFunction "TickOrTock", 0 {
Push "timeDelta", 0.5
SetVariable
"""
W2_TICK_NEW = W2_TICK_OLD + """GetTime
Push "portTimer"
GetVariable
Subtract
Push 25
Less2
If locportfast
Push "timeDelta", 1
SetVariable
locportfast:Push "portTimer"
GetTime
SetVariable
"""

# World 2 pre-renders each level into bitmaps at 1.5x the 720x480 base resolution (meant for big
# monitors). On a 1 GB handheld that runs out of memory in the first level, and a 480p screen
# can't show the extra detail anyway, so cache at 1x.
W2_BITRES_OLD = 'Push "bitRes", 1.5\nDefineLocal\n'
W2_BITRES_NEW = 'Push "bitRes", 1\nDefineLocal\n'

# World 3 caches Level 4 (its "box cache" level) at 1.5x as well, which runs out of memory on
# 1 GB handhelds while the level loads; cache it at 1x like the other levels.
W3_BITRES_OLD = 'Push "bitRes", 1.5\nSetVariable\n'
W3_BITRES_NEW = 'Push "bitRes", 1\nSetVariable\n'

# World 2 kills the player (and a kicked snail shell) once it falls 700 px below the top of the
# view at its lowest scroll: _y > -_root.MinY + 700, where -MinY = level bottom - view height.
# 700 was tuned for the 480 tall view (a 220 px margin below the level), so a taller extend view
# moves the line up: at 720x720 it sits above the level bottom and falling into deep pits kills.
# Use view height + 220, the same margin at every aspect.
W2_FALL_OLD = 'Push 0.0, register2, "MinY"\nGetMember\nSubtract\nPush 700\nAdd2\nGreater\n'
W2_FALL_NEW = ('Push 0.0, register2, "MinY"\nGetMember\nSubtract\nPush register2, "scaledStageHeight"\n'
               'GetMember\nAdd2\nPush 220\nAdd2\nGreater\n')
W2_FALL_SCRIPTS = {"__Packages/CharClass.pcode": "/__Packages/CharClass",
                   "DefineSprite_1399_SnailShell_w2/frame_4/DoAction.pcode": "/DefineSprite_1399_SnailShell_w2/frame_4/DoAction"}

done = {"scrollrect": 0}
for frame in sorted(os.listdir(os.path.join(exp, "scripts"))):
    p = os.path.join(exp, "scripts", frame, "DoAction.pcode")
    if not frame.startswith("frame_") or not os.path.exists(p):
        continue
    src = open(p, encoding="utf-8").read()
    orig = src
    if src.count(SCROLLRECT) == 1:
        src = src.replace(SCROLLRECT, SCROLLRECT + SCROLLRECT.replace('"width", "scaledStageWidth"', '"height", "scaledStageHeight"'))
        done["scrollrect"] += 1
    if 'DefineFunction2 "setBounds", 0,' in src:
        import re
        m = re.search(r'DefineFunction2 "setBounds", 0,.*?Push "stageX"\nGetVariable\nLess2\nNot\nIf (loc[0-9a-f]+)\n', src, re.S)
        old = W3_BOUNDS_OLD.format(end=m.group(1))
        if src.count(old) != 1:
            sys.exit("setBounds anchor not found")
        src = src.replace(old, W3_BOUNDS_NEW.format(end=m.group(1)))
        done["bounds"] = 1
    if src.count(W2_TICK_OLD) == 1:
        src = src.replace(W2_TICK_OLD, W2_TICK_NEW)
        done["tick"] = 1
    if '"World2_LevelProgress"' in src and src.count(W2_BITRES_OLD) == 1:
        src = src.replace(W2_BITRES_OLD, W2_BITRES_NEW)
        done["bitres"] = 1
    if '"startBuildCache"' in src and src.count(W3_BITRES_OLD) == 1:
        src = src.replace(W3_BITRES_OLD, W3_BITRES_NEW)
        done["bitres"] = 1
    if src != orig:
        dst = os.path.join(out, frame + ".pcode")
        open(dst, "w", encoding="utf-8").write(src)
        print(f"/{frame}/DoAction\t{dst}")
if os.path.exists(os.path.join(exp, "scripts", "DefineSprite_1399_SnailShell_w2")):
    for rel, name in W2_FALL_SCRIPTS.items():
        p = os.path.join(exp, "scripts", rel)
        src = open(p, encoding="utf-8").read()
        if src.count(W2_FALL_OLD) != 1:
            sys.exit(f"fall line anchor not found in {rel}")
        dst = os.path.join(out, rel.replace("/", "_"))
        open(dst, "w", encoding="utf-8").write(src.replace(W2_FALL_OLD, W2_FALL_NEW))
        print(f"{name}\t{dst}")
    done["fall"] = 1
if done["scrollrect"] != 1:
    sys.exit(f"ScrollRect anchor matched {done['scrollrect']}x")
print(f"patched OK {done}", file=sys.stderr)
