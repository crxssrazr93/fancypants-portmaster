//! fpa-prep: converts the Adobe ATF textures used by Fancy Pants Adventures World 4 into PNGs
//! that Ruffle can load (Ruffle can't decode lossy ATF, and Mali GPUs can't sample DXT).
//!
//! Usage:
//!   fpa-prep atf <scale> <out_dir> <file.atf>...     convert loose .atf files
//!   fpa-prep swf <scale> <out_dir> <file.swf>        extract + convert ATFs embedded in a SWF
//!
//! ATF v3 formats handled: 0x02 Compressed, 0x04 CompressedAlpha, 0x0C CompressedLossy,
//! 0x0D CompressedLossyAlpha (first mip of first face). Per mip, every record is a u32 BE length
//! plus payload. DXT index bits are LZMA-compressed (5-byte props header, no size field); the DXT
//! endpoint colours/alphas live in a JPEG-XR image of (w/4) x (h/2): top half = endpoint 0 for
//! each 4x4 block, bottom half = endpoint 1. Reference: github.com/adobe/dds2atf pvr2atfcore.cpp.

use std::error::Error;
use std::fs;
use std::io::{Cursor, Read};
use std::path::Path;
use std::time::Instant;

type Res<T> = Result<T, Box<dyn Error>>;

struct Atf<'a> {
    format: u8,
    width: u32,
    height: u32,
    records: Vec<&'a [u8]>,
}

fn parse_atf(d: &[u8]) -> Res<Atf<'_>> {
    if d.len() < 10 || &d[..3] != b"ATF" {
        return Err("not an ATF file".into());
    }
    let (version, mut p) = if d[6] == 0xff { (d[7], 12) } else { (0, 6) };
    let format = d[p] & 0x7f;
    let width = 1u32 << d[p + 1];
    let height = 1u32 << d[p + 2];
    p += 4;
    let n = match format {
        0x02 => 11,
        0x04 => 16,
        0x0c => 12,
        0x0d => 17,
        f => return Err(format!("unsupported ATF format {f:#x}").into()),
    };
    let mut records = Vec::with_capacity(n);
    for _ in 0..n {
        let len = if version == 0 {
            let l = u32::from_be_bytes([0, d[p], d[p + 1], d[p + 2]]) as usize;
            p += 3;
            l
        } else {
            let l = u32::from_be_bytes(d[p..p + 4].try_into()?) as usize;
            p += 4;
            l
        };
        records.push(d.get(p..p + len).ok_or("truncated ATF record")?);
        p += len;
    }
    Ok(Atf { format, width, height, records })
}

/// Raw LZMA stream (props + dict size, no uncompressed-size field) of known output length.
fn lzma_raw(blob: &[u8], expected: usize) -> Res<Vec<u8>> {
    if blob.len() < 5 {
        return Err("empty LZMA record".into());
    }
    let mut src = Vec::with_capacity(blob.len() + 8);
    src.extend_from_slice(&blob[..5]);
    src.extend_from_slice(&(expected as u64).to_le_bytes());
    src.extend_from_slice(&blob[5..]);
    let mut out = Vec::with_capacity(expected);
    lzma_rs::lzma_decompress(&mut Cursor::new(src), &mut out)?;
    if out.len() != expected {
        return Err(format!("LZMA gave {} bytes, expected {expected}", out.len()).into());
    }
    Ok(out)
}

/// Decodes a JPEG-XR endpoint plane; returns raw pixels and bytes per pixel.
fn jxr(blob: &[u8], bw: u32, bh: u32) -> Res<(Vec<u8>, usize)> {
    let mut dec = jpegxr::ImageDecode::with_reader(Cursor::new(blob))?;
    let (w, h) = dec.get_size()?;
    if w as u32 != bw || h as u32 != bh * 2 {
        return Err(format!("JPEG-XR plane {w}x{h}, expected {bw}x{}", bh * 2).into());
    }
    let info = jpegxr::PixelInfo::from_format(dec.get_pixel_format()?);
    let bpp = info.bits_per_pixel() / 8;
    let stride = w as usize * bpp;
    let mut out = vec![0; stride * h as usize];
    dec.copy_all(&mut out, stride)?;
    Ok((out, bpp))
}

/// Endpoint colour as RGB565 (little endian bytes). JPEG-XR planes are 16bpp 565 already, or
/// 24bpp BGR/RGB depending on encoder; handle both.
fn color565(px: &[u8], bpp: usize) -> [u8; 2] {
    match bpp {
        2 => [px[0], px[1]],
        _ => {
            let (r, g, b) = (px[0] as u16, px[1] as u16, px[2] as u16);
            ((r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)).to_le_bytes()
        }
    }
}

fn decode(d: &[u8]) -> Res<(u32, u32, Vec<u32>, u8)> {
    let atf = parse_atf(d)?;
    let (w, h, r) = (atf.width, atf.height, &atf.records);
    let (bw, bh) = ((w / 4).max(1), (h / 4).max(1));
    let n = (bw * bh) as usize;
    let mut pixels = vec![0u32; (w * h) as usize];
    match atf.format {
        0x02 | 0x0c => {
            let bits = lzma_raw(r[0], n * 4)?;
            let (c, cb) = jxr(r[1], bw, bh)?;
            let mut blocks = vec![0u8; n * 8];
            for i in 0..n {
                let b = &mut blocks[i * 8..i * 8 + 8];
                b[0..2].copy_from_slice(&color565(&c[i * cb..], cb));
                b[2..4].copy_from_slice(&color565(&c[(n + i) * cb..], cb));
                b[4..8].copy_from_slice(&bits[i * 4..i * 4 + 4]);
            }
            texture2ddecoder::decode_bc1(&blocks, w as usize, h as usize, &mut pixels)?;
        }
        _ => {
            let abits = lzma_raw(r[0], n * 6)?;
            let (a, ab) = jxr(r[1], bw, bh)?;
            let cbits = lzma_raw(r[2], n * 4)?;
            let (c, cb) = jxr(r[3], bw, bh)?;
            let mut blocks = vec![0u8; n * 16];
            for i in 0..n {
                let b = &mut blocks[i * 16..i * 16 + 16];
                b[0] = a[i * ab];
                b[1] = a[(n + i) * ab];
                b[2..8].copy_from_slice(&abits[i * 6..i * 6 + 6]);
                b[8..10].copy_from_slice(&color565(&c[i * cb..], cb));
                b[10..12].copy_from_slice(&color565(&c[(n + i) * cb..], cb));
                b[12..16].copy_from_slice(&cbits[i * 4..i * 4 + 4]);
            }
            texture2ddecoder::decode_bc3(&blocks, w as usize, h as usize, &mut pixels)?;
        }
    }
    Ok((w, h, pixels, atf.format))
}

fn convert(data: &[u8], scale: f32, out: &Path) -> Res<()> {
    let t = Instant::now();
    let (w, h, pixels, fmt) = decode(data)?;
    // texture2ddecoder emits 0xAARRGGBB
    let mut rgba = Vec::with_capacity(pixels.len() * 4);
    for p in pixels {
        rgba.extend_from_slice(&[(p >> 16) as u8, (p >> 8) as u8, p as u8, (p >> 24) as u8]);
    }
    let mut img = image::RgbaImage::from_raw(w, h, rgba).ok_or("bad image size")?;
    if (scale - 1.0).abs() > f32::EPSILON {
        let (nw, nh) = (((w as f32 * scale).round() as u32).max(1), ((h as f32 * scale).round() as u32).max(1));
        img = image::imageops::resize(&img, nw, nh, image::imageops::FilterType::Triangle);
    }
    let tmp = out.with_extension("png.tmp");
    img.save_with_format(&tmp, image::ImageFormat::Png)?;
    fs::rename(&tmp, out)?;
    println!("OK  {} [{fmt:#04x} {w}x{h}] {:.1}s", out.display(), t.elapsed().as_secs_f32());
    Ok(())
}

/// Returns (name, ATF bytes) for every DefineBinaryData tag holding an ATF texture. Names come
/// from SymbolClass ("Foo_atf_StarlingAssetAtlas" -> "StarlingAssetAtlas").
fn swf_atfs(swf: &[u8]) -> Res<Vec<(String, Vec<u8>)>> {
    let body = match &swf[..3] {
        b"FWS" => swf[8..].to_vec(),
        b"CWS" => {
            let mut v = Vec::new();
            flate2::read::ZlibDecoder::new(&swf[8..]).read_to_end(&mut v)?;
            v
        }
        b"ZWS" => {
            // SWF LZMA: u32 compressed len, 5 props bytes, raw stream
            let len = u32::from_le_bytes(swf[4..8].try_into()?) as usize - 8;
            lzma_raw(&swf[12..], len)?
        }
        _ => return Err("not a SWF".into()),
    };
    let nbits = (body[0] >> 3) as usize;
    let mut p = (5 + nbits * 4 + 7) / 8 + 4;
    let mut bins: Vec<(u16, Vec<u8>)> = Vec::new();
    let mut names = std::collections::HashMap::new();
    while p + 2 <= body.len() {
        let hdr = u16::from_le_bytes([body[p], body[p + 1]]);
        p += 2;
        let code = hdr >> 6;
        let mut len = (hdr & 0x3f) as usize;
        if len == 0x3f {
            len = u32::from_le_bytes(body[p..p + 4].try_into()?) as usize;
            p += 4;
        }
        let tag = &body[p..p + len];
        match code {
            87 if tag.len() > 9 && &tag[6..9] == b"ATF" => {
                bins.push((u16::from_le_bytes([tag[0], tag[1]]), tag[6..].to_vec()))
            }
            76 => {
                let count = u16::from_le_bytes([tag[0], tag[1]]) as usize;
                let mut q = 2;
                for _ in 0..count {
                    let id = u16::from_le_bytes([tag[q], tag[q + 1]]);
                    q += 2;
                    let end = q + tag[q..].iter().position(|&c| c == 0).ok_or("bad SymbolClass")?;
                    names.insert(id, String::from_utf8_lossy(&tag[q..end]).into_owned());
                    q = end + 1;
                }
            }
            0 => break,
            _ => {}
        }
        p += len;
    }
    Ok(bins
        .into_iter()
        .map(|(id, data)| {
            let full = names.get(&id).cloned().unwrap_or_else(|| format!("binary{id}"));
            let short = full.rsplit("_atf_").next().unwrap_or(&full).to_string();
            (short, data)
        })
        .collect())
}

/// Rewrite a zlib-compressed (CWS) SWF uncompressed (FWS), so xdelta patches stay small.
fn inflate(src: &str, dst: &str) -> Res<()> {
    let data = fs::read(src)?;
    let out = match &data[..3] {
        b"CWS" => {
            let mut body = Vec::new();
            flate2::read::ZlibDecoder::new(&data[8..]).read_to_end(&mut body)?;
            [&b"FWS"[..], &data[3..8], &body].concat()
        }
        b"FWS" => data,
        _ => return Err("unsupported SWF compression".into()),
    };
    fs::write(dst, out)?;
    Ok(())
}

/// Scale the pixel coordinates of a Starling texture atlas XML (for a downscaled texture).
fn atlas_xml(factor: f64, src: &str, dst: &str) -> Res<()> {
    const ATTRS: [&str; 10] =
        ["x", "y", "width", "height", "frameX", "frameY", "frameWidth", "frameHeight", "pivotX", "pivotY"];
    let text = fs::read_to_string(src)?;
    let mut out = String::with_capacity(text.len());
    let mut rest = text.as_str();
    while let Some(i) = rest.find("=\"") {
        let (head, tail) = rest.split_at(i);
        let name = head.rsplit(|c: char| c.is_whitespace()).next().unwrap_or("");
        let end = tail[2..].find('"').ok_or("unterminated attribute")? + 2;
        let value = &tail[2..end];
        out.push_str(head);
        match value.parse::<f64>() {
            Ok(v) if ATTRS.contains(&name) => out.push_str(&format!("=\"{}\"", v * factor)),
            _ => out.push_str(&tail[..=end]),
        }
        rest = &tail[end + 1..];
    }
    out.push_str(rest);
    fs::write(dst, out)?;
    Ok(())
}

fn run() -> Res<bool> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 4 && args[1] == "inflate" {
        inflate(&args[2], &args[3])?;
        return Ok(true);
    }
    if args.len() == 5 && args[1] == "atlasxml" {
        atlas_xml(args[2].parse()?, &args[3], &args[4])?;
        return Ok(true);
    }
    if args.len() < 5 {
        eprintln!("usage: fpa-prep atf <scale> <out_dir> <file.atf>...\n       fpa-prep swf <scale> <out_dir> <file.swf>\n       fpa-prep inflate <in.swf> <out.swf>\n       fpa-prep atlasxml <factor> <in.xml> <out.xml>");
        std::process::exit(2);
    }
    let scale: f32 = args[2].parse()?;
    let out_dir = Path::new(&args[3]);
    fs::create_dir_all(out_dir)?;
    let mut ok = true;
    let mut job = |name: &str, data: &[u8]| {
        let out = out_dir.join(format!("{name}.png"));
        if let Err(e) = convert(data, scale, &out) {
            eprintln!("ERR {name}: {e}");
            ok = false;
        }
    };
    match args[1].as_str() {
        "atf" => {
            for f in &args[4..] {
                let stem = Path::new(f).file_stem().ok_or("bad file name")?.to_string_lossy().into_owned();
                job(&stem, &fs::read(f)?);
            }
        }
        "swf" => {
            for (name, data) in swf_atfs(&fs::read(&args[4])?)? {
                job(&name, &data);
            }
        }
        m => return Err(format!("unknown mode {m}").into()),
    }
    Ok(ok)
}

fn main() {
    match run() {
        Ok(true) => {}
        Ok(false) => std::process::exit(1),
        Err(e) => {
            eprintln!("fpa-prep: {e}");
            std::process::exit(1);
        }
    }
}
