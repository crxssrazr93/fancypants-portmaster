#!/usr/bin/env python3
"""swf_inflate.py <in.swf> <out.swf>: rewrite a zlib-compressed (CWS) SWF uncompressed (FWS)."""
import sys, zlib
d = open(sys.argv[1], "rb").read()
if d[:3] == b"CWS":
    d = b"FWS" + d[3:8] + zlib.decompress(d[8:])
elif d[:3] != b"FWS":
    sys.exit("unsupported SWF compression")
open(sys.argv[2], "wb").write(d)
