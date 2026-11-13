"""Paints the calendar picture straight onto a Linux screen (the Pi's HDMI output).

No desktop or browser is involved: the picture is written into the framebuffer,
which is the closest a monitor gets to how the e-ink panel will behave.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

WHITE = (255, 255, 255)


def geometry(device: str = "/dev/fb0") -> tuple[int, int, int, int]:
    """Screen width, height, bits per pixel, and bytes per row."""
    sys = Path("/sys/class/graphics") / Path(device).name
    width, height = (int(v) for v in (sys / "virtual_size").read_text().strip().split(","))
    bpp = int((sys / "bits_per_pixel").read_text().strip())
    try:
        stride = int((sys / "stride").read_text().strip())
    except (OSError, ValueError):
        stride = width * bpp // 8
    return width, height, bpp, stride


def fit(img: Image.Image, width: int, height: int, rotate: int = 0) -> Image.Image:
    """Rotates the picture, then scales it to fit the screen on a white background.

    `rotate` is how far the monitor is turned, in degrees clockwise: 0, 90, 180 or 270.
    """
    if rotate not in (0, 90, 180, 270):
        raise ValueError("rotate must be 0, 90, 180 or 270")
    img = img.convert("RGB")
    if rotate:
        # The monitor is turned clockwise, so the picture turns the other way to stay upright.
        img = img.rotate(rotate, expand=True)
    scale = min(width / img.width, height / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    if size != img.size:
        # NEAREST keeps the six flat panel colours when the size is an exact match or multiple;
        # otherwise smooth scaling reads better on a monitor.
        img = img.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), WHITE)
    canvas.paste(img, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def encode(img: Image.Image, bpp: int, stride: int) -> bytes:
    """Turns an RGB picture into the bytes the framebuffer expects."""
    if bpp == 32:
        data, row = img.tobytes("raw", "BGRX"), img.width * 4
    elif bpp == 24:
        data, row = img.tobytes("raw", "BGR"), img.width * 3
    elif bpp == 16:
        # RGB565, low byte first: gggbbbbb rrrrrggg
        r, g, b = img.split()
        low = ImageChops.add(g.point(lambda v: (v & 0x1C) << 3), b.point(lambda v: v >> 3))
        high = ImageChops.add(r.point(lambda v: v & 0xF8), g.point(lambda v: v >> 5))
        data, row = Image.merge("LA", (low, high)).tobytes(), img.width * 2
    else:
        raise ValueError(f"unsupported screen depth: {bpp} bits per pixel")
    if stride <= row:
        return data
    pad = bytes(stride - row)
    return b"".join(data[i:i + row] + pad for i in range(0, len(data), row))


def show(image_path: str | Path, device: str = "/dev/fb0", rotate: int = 0) -> None:
    """Shows the picture file full screen."""
    width, height, bpp, stride = geometry(device)
    with Image.open(image_path) as img:
        frame = fit(img, width, height, rotate)
    with open(device, "wb") as fb:
        fb.write(encode(frame, bpp, stride))
