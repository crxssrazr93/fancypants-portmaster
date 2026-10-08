#!/usr/bin/env python3
"""Adds test only hooks to a ruffle_sdl source tree (for PC builds, never for the release binary):
  RUFFLE_SDL_SHOT=<f.ppm>   touching <f.ppm>.req saves the next frame to <f.ppm>
                            writing an SDL key name (e.g. "space") to <f.ppm>.key taps that key
Usage: sdl_test_hooks.py <ruffle source dir>   (undo with: git -C <dir> checkout -- sdl/src/main.rs)
The capture reads the window with glReadPixels on the GL context wgpu shares. wgpu leaves its
pixel pack state set after a texture readback (BitmapData.colorTransform and similar): a bound
pack buffer made every capture of such a level all black, and its row length made glReadPixels
write past the buffer (a crash). The hook resets that state for its read and restores it after.
"""
import sys
p=sys.argv[1]+'/sdl/src/main.rs'; s=open(p).read()
s=s.replace("""    let target = SdlTarget {
        gl,""","""    let shot_gl = gl.clone();
    let target = SdlTarget {
        gl,""",1)
old="""                window.gl_swap_window();"""
new="""                if let Some(shot) = std::env::var_os("RUFFLE_SDL_SHOT") {
                    let req = std::path::PathBuf::from(format!("{}.req", shot.to_string_lossy()));
                    if req.exists() {
                        let (w, h) = window.drawable_size();
                        let mut px = vec![0u8; (w * h * 4) as usize];
                        unsafe {
                            // wgpu reads textures back (BitmapData readbacks) through a pixel
                            // pack buffer with its own row length and leaves both set: with the
                            // buffer bound glReadPixels writes into it (px stays all zero), and
                            // with only the row length left it writes past the end of px. Both
                            // are reset for the read and put back after, as wgpu tracks them.
                            let pack = shot_gl.get_parameter_i32(glow::PIXEL_PACK_BUFFER_BINDING);
                            let align = shot_gl.get_parameter_i32(glow::PACK_ALIGNMENT);
                            let row_len = shot_gl.get_parameter_i32(glow::PACK_ROW_LENGTH);
                            let skip_rows = shot_gl.get_parameter_i32(glow::PACK_SKIP_ROWS);
                            let skip_px = shot_gl.get_parameter_i32(glow::PACK_SKIP_PIXELS);
                            shot_gl.pixel_store_i32(glow::PACK_ROW_LENGTH, 0);
                            shot_gl.pixel_store_i32(glow::PACK_SKIP_ROWS, 0);
                            shot_gl.pixel_store_i32(glow::PACK_SKIP_PIXELS, 0);
                            let read_fb = shot_gl.get_parameter_i32(glow::READ_FRAMEBUFFER_BINDING);
                            shot_gl.bind_buffer(glow::PIXEL_PACK_BUFFER, None);
                            shot_gl.pixel_store_i32(glow::PACK_ALIGNMENT, 1);
                            shot_gl.bind_framebuffer(glow::READ_FRAMEBUFFER, None);
                            shot_gl.read_pixels(0, 0, w as i32, h as i32, glow::RGBA, glow::UNSIGNED_BYTE,
                                glow::PixelPackData::Slice(Some(&mut px)));
                            shot_gl.bind_buffer(glow::PIXEL_PACK_BUFFER,
                                std::num::NonZeroU32::new(pack as u32).map(glow::NativeBuffer));
                            shot_gl.pixel_store_i32(glow::PACK_ALIGNMENT, align);
                            shot_gl.pixel_store_i32(glow::PACK_ROW_LENGTH, row_len);
                            shot_gl.pixel_store_i32(glow::PACK_SKIP_ROWS, skip_rows);
                            shot_gl.pixel_store_i32(glow::PACK_SKIP_PIXELS, skip_px);
                            shot_gl.bind_framebuffer(glow::READ_FRAMEBUFFER,
                                std::num::NonZeroU32::new(read_fb as u32).map(glow::NativeFramebuffer));
                        }
                        let mut out = format!("P6 {w} {h} 255\\n").into_bytes();
                        for y in (0..h).rev() {
                            for x in 0..w {
                                let i = ((y * w + x) * 4) as usize;
                                out.extend_from_slice(&px[i..i + 3]);
                            }
                        }
                        let _ = std::fs::write(&shot, out);
                        let _ = std::fs::remove_file(&req);
                    }
                }
                window.gl_swap_window();"""
assert s.count(old)==1; s=s.replace(old,new)
old2='''        let mut wait = next_frame.saturating_duration_since(Instant::now());'''
new2='''        if let Some(shot) = std::env::var_os("RUFFLE_SDL_SHOT") {
            let kf = format!("{}.key", shot.to_string_lossy());
            if let Ok(name) = std::fs::read_to_string(&kf) {
                let _ = std::fs::remove_file(&kf);
                let name = name.trim();
                let sc = sdl2::keyboard::Scancode::from_name(name);
                let kc = sdl2::keyboard::Keycode::from_name(name);
                let mut player = player.lock().expect("player lock");
                player.handle_event(PlayerEvent::KeyDown {
                    key: keys::key_descriptor(sc, kc, sdl2::keyboard::Mod::NOMOD),
                });
                held_ups.push((
                    Instant::now() + Duration::from_millis(150),
                    format!("test{name}"),
                    PlayerEvent::KeyUp { key: keys::key_descriptor(sc, kc, sdl2::keyboard::Mod::NOMOD) },
                ));
            }
        }
'''+old2
assert s.count(old2)==1; s=s.replace(old2,new2)
open(p,'w').write(s)
