#!/usr/bin/env python3
"""Let the AS2 worlds (FPAWorld1-3) use a screen narrower than 3:2 (4:3 handhelds).

The worlds already support wider screens: SetDimensions() derives scaledStageWidth/Height from the
aspect the shell reports. For narrower screens it computes the taller height but
 * only widens the camera clip (ScrollRect), so the bottom of the view stayed blank, and
 * World 3's setBounds() only centres rooms narrower than the view, so in rooms shorter than the
   view the vertical camera clamp flipped between top and bottom every few frames,
 * World 1's camera bounds are fixed numbers for the 480 tall view, so its lowest camera position
   showed the space below the level (a bar at the bottom of the screen), and World 2 extended
   rooms shorter than the view downwards, with the same bar,
 * the pause overlays are drawn for a 480 tall view, so the bottom of a taller screen stayed
   uncovered while paused.
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

# World 3 setBounds(): rooms shorter than the view keep their floor at the bottom of the screen
# (the extra height shows above the room), as World 1 and 2 now do
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
Push "MaxY", "MinY"
GetVariable
Push "stageY"
GetVariable
Add2
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

# World 1 setBounds(): the bounds table is for a 480 tall view. Raise the lowest camera position by
# the extra height so the view's bottom stays at the level's bottom; rooms that become shorter than
# the view keep their floor at the bottom (MaxY = MinY).
W1_BOUNDS_OLD = 'Push 3\nGetMember\nSetVariable\nPush "widescreenOffset", "scaledStageWidthHalf"\n'
W1_BOUNDS_NEW = """Push 3
GetMember
SetVariable
Push "MinY", "MinY"
GetVariable
Push "scaledStageHeight"
GetVariable
Push 480
Subtract
Add2
SetVariable
Push "MaxY"
GetVariable
Push "MinY"
GetVariable
Less2
Not
If locportmy
Push "MaxY", "MinY"
GetVariable
SetVariable
locportmy:Push "widescreenOffset", "scaledStageWidthHalf"
"""

# World 2 setBounds(): a room shorter than the view grew downwards (realMaxY = realMinY + height);
# grow it upwards instead, so its floor stays at the bottom of the screen.
W2_SHORT_OLD = 'Push "realMaxY", "realMinY"\nGetVariable\nPush "scaledStageHeight"\nGetVariable\nAdd2\nSetVariable\n'
W2_SHORT_NEW = 'Push "realMinY", "realMaxY"\nGetVariable\nPush "scaledStageHeight"\nGetVariable\nSubtract\nSetVariable\n'

# Pause overlays: portPauseFill(clip) draws black inside the newly attached pause clip from just
# above the bottom of the 480 tall design down past the bottom of a taller view.
PAUSE_FILL_FN = """DefineFunction "portPauseFill", 1, "m" {
Push "scaledStageHeight"
GetVariable
Push 480
Greater
Not
If locportpf
Push "f", 9999, "portFill", 2, "m"
GetVariable
Push "createEmptyMovieClip"
CallMethod
DefineLocal
Push 100, 0.0, 2, "f"
GetVariable
Push "beginFill"
CallMethod
Pop
Push 470, -2000, 2, "f"
GetVariable
Push "moveTo"
CallMethod
Pop
Push 470, 4000, 2, "f"
GetVariable
Push "lineTo"
CallMethod
Pop
Push 4000, 4000, 2, "f"
GetVariable
Push "lineTo"
CallMethod
Pop
Push 4000, -2000, 2, "f"
GetVariable
Push "lineTo"
CallMethod
Pop
Push 0.0, "f"
GetVariable
Push "endFill"
CallMethod
Pop
locportpf:Push 0.0
Pop
}
"""
PAUSE_ATTACHES = ['Push "PauseMenu", "PauseMenu", 4, "attachMovie"\nCallFunction\nPop\n',
                  'Push 100002, "PauseMenu", "PauseMenu", 4, "attachMovie"\nCallFunction\nPop\n',
                  'Push "PauseMenu", "PauseMenu_w3", 3, "OutPut"\nGetVariable\nPush "attachMovie"\nCallMethod\nPop\n']

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
    if '"setBounds"' in src and src.count(W1_BOUNDS_OLD) == 1:
        src = src.replace(W1_BOUNDS_OLD, W1_BOUNDS_NEW)
        done["w1bounds"] = 1
    if src.count(W2_SHORT_OLD) == 1:
        src = src.replace(W2_SHORT_OLD, W2_SHORT_NEW)
        done["w2short"] = 1
    pauses = sum(src.count(a) for a in PAUSE_ATTACHES)
    if pauses:
        for a in PAUSE_ATTACHES:
            # the attached clip, left on the stack, becomes portPauseFill's argument
            src = src.replace(a, a[:-len("Pop\n")] + 'Push 1, "portPauseFill"\nCallFunction\nPop\n')
        first_nl = src.index("\n") + 1  # after the ConstantPool line
        src = src[:first_nl] + PAUSE_FILL_FN + src[first_nl:]
        done["pause"] = done.get("pause", 0) + pauses
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
