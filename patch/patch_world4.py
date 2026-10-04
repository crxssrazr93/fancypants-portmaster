#!/usr/bin/env python3
"""Patch World 4 (Starling/Stage3D) scripts so they load PNG textures by URL in Ruffle.

AIR's File.applicationDirectory/resolvePath and directory listings don't work in Ruffle, and
Ruffle can't decode the lossy ATF textures (nor upload DXT on Mali GPUs). The port converts every
.atf to a (downscaled) .png at install time; this patch makes the game load those PNGs.

Usage: patch_world4.py <dec/scripts dir> <World4 dir> <out dir> <texture_scale>
  texture_scale: Starling scale of the converted PNGs (0.5 = half-resolution textures)
Writes patched Main.as and StarlingBackgrounds.as into <out dir>.
"""
import os
import sys

scripts, world4, out, scale = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])


def patcher(path):
    src = open(path, encoding="utf-8").read()

    def sub(old, new, count=1):
        nonlocal src
        n = src.count(old)
        if n != count:
            sys.exit(f"{os.path.basename(path)}: anchor matched {n}x (expected {count}): {old[:90]!r}")
        src = src.replace(old, new)

    return sub, lambda: src


# ---- Main.as -----------------------------------------------------------------------------------
sub, result = patcher(os.path.join(scripts, "Main.as"))

# Level texture folders: AssetManager.enqueue(File dir) lists the directory. Replace with an
# explicit manifest of the converted PNG (+ atlas XML) files, built from the install's assets dir.
manifest = {}
assets = os.path.join(world4, "assets")
for level in sorted(os.listdir(assets)):
    files = []
    for f in sorted(os.listdir(os.path.join(assets, level))):
        base, ext = os.path.splitext(f)
        if ext == ".atf":
            files.append(base + ".png")
        elif ext == ".xml":
            files.append(f)
    manifest[level] = files
as3_manifest = "{" + ",".join(
    '"%s":[%s]' % (k, ",".join('"%s"' % f for f in v)) for k, v in manifest.items()
) + "}"

enqueue_dir = """
      private static const PORT_LEVEL_FILES:Object = %s;

      private function portEnqueueLevel(dir:String) : void
      {
         var files:Array = PORT_LEVEL_FILES[this.LoadIt] as Array;
         var i:uint = 0;
         this.levelTexturesManager.scaleFactor = %s;
         if(files == null)
         {
            return;
         }
         for(i = 0; i < files.length; i++)
         {
            this.levelTexturesManager.enqueue(dir + "/" + files[i]);
         }
      }
""" % (as3_manifest, repr(scale))

sub(
    '            this.levelTexturesManager.enqueue(this.appDir.resolvePath("assets/" + this.LoadIt));',
    '            this.portEnqueueLevel("assets/" + this.LoadIt);',
)
sub(
    '            this.levelTexturesManager.enqueue(this.appDir.resolvePath("World4/assets/" + this.LoadIt));',
    '            this.portEnqueueLevel("World4/assets/" + this.LoadIt);',
)
sub("      private function NewTextureLoader() : void\n", enqueue_dir + "\n      private function NewTextureLoader() : void\n")

# remaining single-file loads: plain relative URLs instead of File objects
sub("this.appDir.resolvePath(", "(", count=4)

# dev-only writers (debug builds dump PNG/XML next to the app); make them no-ops
for fn in ("SavePNG(bitmap:BitmapData, filename:String)", "SaveXML(xml:XML, filename:String)"):
    head = "      public function " + fn + " : void\n      {\n"
    src0 = result()
    i = src0.index(head) + len(head)
    j = src0.index("\n      }\n", i)
    sub(src0[i:j], "")

# AIR-only APIs: JPEXS compiles against playerglobal, and Ruffle only stubs them anyway
sub("   import flash.desktop.*;\n", "")
sub("   import flash.filesystem.*;\n", "")
sub("      private var appDir:File = File.applicationDirectory;\n", "")
sub(
    """            stage.nativeWindow.x = 100;
            stage.nativeWindow.y = 100;
            stage.nativeWindow.width = Capabilities.screenResolutionX / 2 + 100;
            stage.nativeWindow.height = Capabilities.screenResolutionY / 2 + 100;
""",
    "",
)
sub("            NativeApplication.nativeApplication.addEventListener(KeyboardEvent.KEY_DOWN,this.CheckBackButton);\n", "")
sub("         NativeApplication.nativeApplication.exit();", '         fscommand("quit");')
_left = [w for w in ("File.", "FileStream", "FileMode", "NativeApplication", "nativeWindow", "appDir") if w in result()]
if _left:
    sys.exit(f"Main.as: leftover AIR references: {_left}")

# JPEXS renders "var f:Function = function():*{}" fields as empty methods; assigning to them
# then fails at runtime ("Cannot assign to a method"). Turn assigned ones back into Function vars.
import re as _re
_src = result()
for _m in list(_re.finditer(r"\n      (private|public|internal) function (\w+)\(\):\*\n      \{\n      \}\n", _src)):
    if _re.search(r"\." + _m.group(2) + r" = ", _src):
        sub(_m.group(0), "\n      %s var %s:Function = function():*\n      {\n      };\n" % (_m.group(1), _m.group(2)))

# JPEXS decompiles some Starling types unqualified; with both flash.* and starling.* wildcard
# imports they'd recompile to the flash.* class. Qualify the ones that matter.
sub("         Texture.fromEmbeddedAsset(", "         starling.textures.Texture.fromEmbeddedAsset(")
open(os.path.join(out, "Main.as"), "w", encoding="utf-8").write(result())

# ---- StarlingBackgrounds.as --------------------------------------------------------------------
sub, result = patcher(os.path.join(scripts, "StarlingBackgrounds.as"))
sub(
    """         Texture.fromAtfData(new this.atf_StarlingAssetAtlas(),1.6,false,this.onTextureLoaded,false);
         if(lighting)
         {
            Texture.fromAtfData(new this.atf_StarlingAssetAtlas_n(),1.6,false,this.onTextureLoaded_n,false);
         }""",
    """         this.portLoadPng("World4/assets/_embedded/StarlingAssetAtlas.png",this.onTextureLoaded);
         if(lighting)
         {
            this.portLoadPng("World4/assets/_embedded/StarlingAssetAtlas_n.png",this.onTextureLoaded_n);
         }""",
)
# embedded ATF atlases are extracted + converted to PNG by the port's prep tool
sub(
    "      public function LoadStarlingAssetAtlas() : void\n",
    """      private function portLoadPng(url:String, done:Function) : void
      {
         var loader:flash.display.Loader = new flash.display.Loader();
         loader.contentLoaderInfo.addEventListener(flash.events.Event.COMPLETE,function(e:flash.events.Event):void
         {
            var bmp:BitmapData = Bitmap(loader.content).bitmapData;
            trace("[port] loaded " + url + " " + bmp.width + "x" + bmp.height);
            done(Texture.fromBitmapData(bmp,false,false,%s));
         });
         loader.contentLoaderInfo.addEventListener(flash.events.IOErrorEvent.IO_ERROR,function(e:flash.events.IOErrorEvent):void
         {
            trace("[port] FAILED to load " + url + ": " + e.text);
         });
         loader.load(new flash.net.URLRequest(url));
      }

      public function LoadStarlingAssetAtlas() : void
""" % repr(round(1.6 * scale, 6)),
)
# The atlas XML is in pixels of the original texture and Starling divides it by texture.scale.
# Our PNG has a fraction of the pixels (and of the scale), so scale the XML to match.
sub(
    "new TextureAtlas(texture,XML(new this.xml_StarlingAssetAtlas()))",
    "new TextureAtlas(texture,this.portScaleAtlasXml(new this.xml_StarlingAssetAtlas()))",
    count=2,
)
sub(
    "      public function LoadStarlingAssetAtlas() : void\n",
    """      private function portScaleAtlasXml(data:Object) : XML
      {
         var s:String = XML(data).toXMLString();
         s = s.replace(/ (x|y|width|height|frameX|frameY|frameWidth|frameHeight|pivotX|pivotY)="(-?[0-9.]+)"/g,function():String
         {
            return " " + arguments[1] + '="' + Number(arguments[2]) * %s + '"';
         });
         return XML(s);
      }

      public function LoadStarlingAssetAtlas() : void
""" % repr(scale),
)
sub("         this.StaticBackground = new Sprite();", "         this.StaticBackground = new starling.display.Sprite();")
open(os.path.join(out, "StarlingBackgrounds.as"), "w", encoding="utf-8").write(result())
# ---- starling/textures/ConcretePotTexture.as ------------------------------------------------------
# Non power-of-two bitmaps (like the per-frame character bitmap) are padded with copyPixels, which
# in Ruffle reads a freshly drawn (GPU-side) bitmap back to the CPU and stalls every frame.
# draw() onto the transparent buffer gives the same pixels and stays on the GPU.
sub, result = patcher(os.path.join(scripts, "starling", "textures", "ConcretePotTexture.as"))
sub("            buffer.copyPixels(data,data.rect,sOrigin);", "            buffer.draw(data);")
os.makedirs(os.path.join(out, "starling", "textures"), exist_ok=True)
open(os.path.join(out, "starling", "textures", "ConcretePotTexture.as"), "w", encoding="utf-8").write(result())
print("patched OK")
