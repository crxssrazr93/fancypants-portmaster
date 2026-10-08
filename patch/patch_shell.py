#!/usr/bin/env python3
"""Patch the decompiled Classic Pack shell (SuperLoaderMain.as) so it runs in Ruffle.

Removes Steamworks (ANE), AIR NativeApplication/NativeWindow/File usage and GameInput,
stores settings in a local SharedObject instead of Steam Cloud, and quits via fscommand.
Usage: patch_shell.py <in.as> <out.as>
"""
import re
import sys

src = open(sys.argv[1], encoding="utf-8").read()


def sub(old, new, count=1):
    global src
    n = src.count(old)
    if n != count:
        sys.exit(f"patch anchor matched {n}x (expected {count}): {old[:80]!r}")
    src = src.replace(old, new)


def drop_method(name):
    """Remove a whole method body by brace matching."""
    global src
    m = re.search(r"\n      (?:private|public|internal) function " + name + r"\(", src)
    if not m:
        sys.exit(f"method not found: {name}")
    i = src.index("{", m.end())
    depth = 0
    j = i
    while True:
        c = src[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    src = src[: m.start()] + src[j + 1 :]


# imports: drop Steam ANE and AIR-only packages
sub("   import com.amanitadesign.steam.*;\n", "")
sub("   import flash.desktop.*;\n", "")
sub("   import flash.filesystem.*;\n", "")

# fields
sub("      private var gameInputClass:GameInput;\n", "")
sub("      private var Steamworks:FRESteamWorks;\n", "")
sub("         this.Steamworks = new FRESteamWorks();\n", "")

# constructor: Steam init, native window sizing, GameInput, AIR listeners
sub(
    """         try
         {
            this.Steamworks.init();
            this.log("running Steamworks appID:" + this.Steamworks.getAppID());
            if(this.Steamworks.getAppID() != 1668460)
            {
               vhgdhj.hhfad;
            }
            this.Steamworks.inputInit();
            this.Steamworks.addEventListener(SteamEvent.STEAM_RESPONSE,this.onSteamResponse);
         }
         catch(err:Error)
         {
            NativeApplication.nativeApplication.exit();
            return;
         }
""",
    "",
)
sub(
    """         stage.nativeWindow.x = 200;
         stage.nativeWindow.y = 200;
         originalRatio = this.originalStageWidth / this.originalStageHeight;
         stage.nativeWindow.height = Capabilities.screenResolutionY / 2;
         stage.nativeWindow.width = stage.nativeWindow.height * originalRatio;
         this.gameInputClass = new GameInput();
         this.gameInputClass.addEventListener(GameInputEvent.DEVICE_ADDED,this.controllerAdded);
         this.gameInputClass.addEventListener(GameInputEvent.DEVICE_REMOVED,this.controllerRemoved);
""",
    "",
)
sub(
    """         stage.nativeWindow.addEventListener(NativeWindowBoundsEvent.RESIZING,this.onResizingWindow);
         stage.nativeWindow.addEventListener(NativeWindowBoundsEvent.MOVING,this.onMovingWindow);
         NativeApplication.nativeApplication.addEventListener(KeyboardEvent.KEY_DOWN,this.CheckBackButton);
         stage.nativeWindow.addEventListener(Event.CLOSING,this.onCloseCall);
""",
    "",
)
# always run "fullscreen" (the device screen is the window)
sub("         this.LoadGameData();\n         stage.align", "         this.LoadGameData();\n         this.SaveData.fullscreen = true;\n         stage.align")

# optional flashvars to boot straight into a world: -Pgame=World1 -Plevel=Menus1 -Pdoor=-1
sub(
    "         this.startControls();\n         this.LoadGame(this.GameIt,this.LoadIt,this.DoorIt);",
    """         if(loaderInfo.parameters.game)
         {
            this.GameIt = String(loaderInfo.parameters.game);
            this.LoadIt = loaderInfo.parameters.level ? String(loaderInfo.parameters.level) : "Menus1";
            this.DoorIt = loaderInfo.parameters.door ? int(loaderInfo.parameters.door) : 0;
         }
         this.startControls();
         this.LoadGame(this.GameIt,this.LoadIt,this.DoorIt);""",
)

# methods that only exist for AIR windows / GameInput / Steam
for name in (
    "controlsChanged",
    "controllerAdded",
    "controllerRemoved",
    "setupGamepad",
    "onMovingWindow",
    "onResizingWindow",
    "CheckBackButton",
    "onCloseCall",
    "launchSteamVersion",
    "restartApplication",
    "onSteamResponse",
):
    drop_method(name)

# window dragging/resizing on mouse down
sub(
    """            if(mouseX > stage.stageWidth - 50 && mouseY > stage.stageHeight - 50)
            {
               stage.nativeWindow.startResize("BR");
            }
            else
            {
               stage.nativeWindow.startMove();
               this.mouseIsDown = true;
               this.mouseDownPos.x = stage.nativeWindow.x;
               this.mouseDownPos.y = stage.nativeWindow.y;
               Mouse.cursor = "hand";
            }
""",
    """            this.mouseIsDown = true;
""",
)
sub(
    """         else if(!this.SaveData.fullscreen)
         {
            if(e.stageX > stage.stageWidth - 50 && e.stageY > stage.stageHeight - 50)
            {
               stage.nativeWindow.startResize("BR");
            }
            else
            {
               stage.nativeWindow.startMove();
               this.mouseIsDown = true;
               this.mouseDownPos.x = stage.nativeWindow.x;
               this.mouseDownPos.y = stage.nativeWindow.y;
               Mouse.cursor = "hand";
            }
         }
""",
    "",
)
# dead references the decompiler surfaced (not defined anywhere)
sub("            removeEventListener(Event.ENTER_FRAME,menuEnterFrame);\n", "")
sub("            sendSettingsWaitN = 0;\n", "")

# fullscreen toggle button: keep fullscreen, nothing to toggle on a handheld
sub("            this.SaveData.fullscreen = !this.SaveData.fullscreen;\n", "")

# windowed branch of SetupScreen is unreachable now; strip its nativeWindow use
sub(
    """            this.rawStageWidth = stage.nativeWindow.width;
            this.rawStageHeight = stage.nativeWindow.height;
""",
    """            this.rawStageWidth = stage.stageWidth;
            this.rawStageHeight = stage.stageHeight;
""",
)
sub(
    """            stage.nativeWindow.width = this.rawStageWidth;
            stage.nativeWindow.height = this.rawStageHeight;
""",
    "",
)
sub(
    """            if(!this.SaveData.fullscreen)
            {
               stage.nativeWindow.width += this.debug.width;
            }
""",
    "",
)

# Native aspect ratio for the AS2 worlds ("compatibility" mode). The original renders at the
# screen's aspect via stage.fullScreenSourceRect, which Ruffle doesn't implement, so it fell back
# to SHOW_ALL letterboxing. Instead: no stage scaling, scale the game to the screen height and
# center it horizontally for fit and fill. In extend mode the world itself widens its view to the
# screen (setDimensions), so it starts at the left edge: centering it there pushed a 16:9 view
# half a margin to the right (white strip on the left, the right edge cut off).
sub(
    """         if(this.compatibility)
         {
            stage.scaleMode = StageScaleMode.NO_SCALE;
            stage.scaleMode = StageScaleMode.SHOW_ALL;
         }""",
    """         if(this.compatibility)
         {
            stage.scaleMode = StageScaleMode.SHOW_ALL;
            stage.scaleMode = StageScaleMode.NO_SCALE;
         }""",
)
sub(
    """         if(this.compatibility)
         {
            scaleX = scaleY = this.Scale;
         }
         else
         {
            scaleX = scaleY = 1;
         }""",
    """         if(this.compatibility)
         {
            if(loaderInfo.parameters.aspect == "fill")
            {
               this.Scale = Math.max(stage.stageWidth / this.originalStageWidth,stage.stageHeight / this.originalStageHeight);
            }
            else
            {
               this.Scale = Math.min(stage.stageWidth / this.originalStageWidth,stage.stageHeight / this.originalStageHeight);
            }
            scaleX = scaleY = this.Scale;
            if(loaderInfo.parameters.aspect == "extend")
            {
               x = 0;
            }
            else
            {
               x = Math.round((stage.stageWidth - this.originalStageWidth * this.Scale) / 2);
            }
            if(loaderInfo.parameters.aspect == "fit")
            {
               y = Math.round((stage.stageHeight - this.originalStageHeight * this.Scale) / 2);
            }
            else
            {
               y = 0;
            }
            if(this.portBackdrop == null)
            {
               this.portBackdrop = new Shape();
               stage.addChildAt(this.portBackdrop,0);
            }
            this.portBackdrop.graphics.clear();
            this.portBackdrop.graphics.beginFill(0);
            this.portBackdrop.graphics.drawRect(0,0,stage.stageWidth,stage.stageHeight);
            this.portBackdrop.graphics.endFill();
            this.portBackdrop.graphics.beginFill(16777215);
            if(loaderInfo.parameters.aspect == "fit")
            {
               this.portBackdrop.graphics.drawRect(x,y,this.originalStageWidth * this.Scale,this.originalStageHeight * this.Scale);
            }
            else
            {
               this.portBackdrop.graphics.drawRect(0,0,stage.stageWidth,stage.stageHeight);
            }
            this.portBackdrop.graphics.endFill();
            this.portBackdrop.visible = true;
            if(this.portBars == null)
            {
               this.portBars = new Shape();
               stage.addChild(this.portBars);
            }
            this.portBars.graphics.clear();
            if(loaderInfo.parameters.aspect == "fit")
            {
               this.portBars.graphics.beginFill(0);
               this.portBars.graphics.drawRect(0,0,stage.stageWidth,stage.stageHeight);
               this.portBars.graphics.drawRect(x,y,this.originalStageWidth * this.Scale,this.originalStageHeight * this.Scale);
               this.portBars.graphics.endFill();
            }
            this.portBars.visible = true;
         }
         else
         {
            scaleX = scaleY = 1;
            x = 0;
            y = 0;
            if(this.portBackdrop != null)
            {
               this.portBackdrop.visible = false;
            }
            if(this.portBars != null)
            {
               this.portBars.visible = false;
            }
         }""",
)

# The AS2 worlds widen/heighten their own camera from the size the shell reports via
# setDimensions. Report the real stage (window) size rather than Capabilities.screenResolution,
# which under Westonpack/Xvfb needn't match the window.
sub("""            this.screenRatio = newRatio = Capabilities.screenResolutionX / Capabilities.screenResolutionY;
            if(this.compatibility)
            {
""",
    """            this.screenRatio = newRatio = stage.stageWidth / stage.stageHeight;
            if(this.compatibility)
            {
               if(loaderInfo.parameters.aspect != "extend")
               {
                  this.screenRatio = newRatio = this.originalStageWidth / this.originalStageHeight;
               }
""")
# backdrop behind the scaled game: white like the original stage colour (levels rely on it),
# with black bars outside the game area in fit mode. The worlds draw level art past their own
# view, so in fit mode a frame on top of everything (a stage child above the shell) covers the bars.
sub("      private var screenRatio:Number;\n", "      private var screenRatio:Number;\n\n      private var portBackdrop:Shape;\n\n      private var portBars:Shape;\n")
sub("               if(this.rawStageHeight > Capabilities.screenResolutionY)\n               {\n                  this.rawStageHeight = Capabilities.screenResolutionY;",
    "               if(this.rawStageHeight > stage.stageHeight)\n               {\n                  this.rawStageHeight = stage.stageHeight;")

# The shell keeps every world it has loaded (hidden) for quick returns. A 1 GB handheld can't hold
# the Stage3D hub and an AS2 world at once, so switching to another world restarts Ruffle instead
# (fscommand "relaunch", handled by the port's run-ruffle), and background preloading is off.
sub(
    """      private function LoadGame(game:String, level:String, door:int) : void
      {
         var n:uint = 0;
""",
    """      private function LoadGame(game:String, level:String, door:int) : void
      {
         var n:uint = 0;
         if(this.GameNameArray.length > 0 && this.GameNameArray.indexOf(game) == -1)
         {
            this.SaveGameData();
            fscommand("relaunch",game + " " + level + " " + door);
            return;
         }
""",
)
sub(
    """      private function preLoadGame(game:String, level:String, door:int) : void
      {
""",
    """      private function preLoadGame(game:String, level:String, door:int) : void
      {
         return;
""",
)

# Worlds 1 and 2 ran at 60 fps with a 30 Hz game clock. Handheld CPUs land between 30 and 60, where
# their speed wobbles, so run them at a steady 30 fps like World 3 (flashvar worldfps=60 restores 60).
sub(
    """         if(game == "World3")
         {
            stage.frameRate = 30;""",
    """         if(game == "World3" || game != "World4" && loaderInfo.parameters.worldfps != "60")
         {
            stage.frameRate = 30;""",
)

# quitting
sub("NativeApplication.nativeApplication.exit();", 'fscommand("quit");', count=2)

# Steam Cloud -> local SharedObject
sub(
    """         var dataOut:ByteArray = new ByteArray();
         dataOut.writeUTFBytes(data);
         return this.Steamworks.fileWrite(fileName,dataOut);""",
    """         var so:SharedObject = SharedObject.getLocal("FPAClassicPack","/");
         so.data[fileName] = data;
         so.flush();
         return true;""",
)
sub(
    """         var dataIn:ByteArray = new ByteArray();
         if(this.Steamworks.fileRead(fileName,dataIn))
         {
            return dataIn.readUTFBytes(dataIn.length);
         }
         return "";""",
    """         var so:SharedObject = SharedObject.getLocal("FPAClassicPack","/");
         if(so.data[fileName] is String)
         {
            return so.data[fileName];
         }
         return "";""",
)

leftover = [w for w in ("Steamworks", "nativeWindow", "NativeApplication", "GameInput", "File.") if w in src]
if leftover:
    sys.exit(f"leftover AIR/Steam references: {leftover}")
open(sys.argv[2], "w", encoding="utf-8").write(src)
print("patched OK")
