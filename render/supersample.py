"""Stills for the live renders (render/live_render.py, render/live_photo.py), in a RUNNING Blender.

gpu_only(): Cycles on the GPU alone, OptiX first, whatever the preferences say.  A fresh Blender has
none set, and a CPU left ticked beside the GPU takes tiles and slows the render.  Session only, never
saved.

still(): the scene rendered at SS times the size, then each SS x SS block averaged (supersampling).
Thin edges (layer lines, pins, cables) stay crisp where the denoiser and the 1.5 px pixel filter would
smear them at 1x.  The averaging is done in linear float, so the colours round-trip.
"""

from pathlib import Path

import bpy
import numpy as np

SS = 2


def gpu_only():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except Exception:
            continue
        if any(d.type == backend for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == backend
            return "GPU"
    return "CPU"


def still(sc, out, w, h, samples, ss=SS, noise=0.008, quality=92):
    """Render scene `sc` to `out` (.jpg or .png) at w x h, through an ss x ss supersample."""
    sc.render.resolution_x, sc.render.resolution_y = w * ss, h * ss
    sc.render.resolution_percentage = 100
    sc.cycles.device = gpu_only()
    sc.cycles.samples = samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = noise
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = True
    tmp = str(Path(bpy.app.tempdir or ".") / f"{sc.name}-ss.png")
    sc.render.filepath = tmp
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0], scene=sc):
        bpy.ops.render.render(write_still=True, scene=sc.name)
    big = bpy.data.images.load(tmp, check_existing=False)
    px = np.empty(w * ss * h * ss * 4, dtype=np.float32)
    big.pixels.foreach_get(px)
    px = px.reshape(h, ss, w, ss, 4).mean(axis=(1, 3))
    # a 16-bit PNG loads as a float buffer, in linear: average there, into a float image, which the save
    # encodes back to sRGB (a byte image would take the linear values as display values: too dark)
    img = bpy.data.images.new(f"{sc.name}-still", w, h, alpha=False, float_buffer=True)
    img.pixels.foreach_set(px.ravel())
    img.file_format = "JPEG" if out.lower().endswith((".jpg", ".jpeg")) else "PNG"
    img.save(filepath=out, quality=quality)
    bpy.data.images.remove(img)
    bpy.data.images.remove(big)
    return {"out": out, "size": [w, h], "samples": samples, "supersample": ss, "device": sc.cycles.device}
