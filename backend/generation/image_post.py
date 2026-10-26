"""Image post-processing — owner-approved additions 2026-10-25 (QA "world best" image audit; not in the PRD, docs/PRD_GAPS.md §0).

The image model only draws 1024x1024, 1536x1024 or 1024x1536. Delivery files (exact banner sizes, emote packs) are made here
with Pillow (implementation necessity, docs/PRD_GAPS.md), and the checks a human art director would do are measured here:
real transparency, artwork touching the frame (a cut-off sticker cannot be die-cut)."""
from __future__ import annotations

import io

from PIL import Image

# Asset type -> delivery files. Sizes are the platforms' published specs (Twitch emotes 112/56/28, sub badges 72/36/18,
# profile banner 1200x480, offline screen 1920x1080; YouTube banner 2560x1440, thumbnail 1280x720; Discord emote 128).
PACKS = {"twitch_emote": [(112, 112), (56, 56), (28, 28)], "twitch_badge": [(72, 72), (36, 36), (18, 18)],
         "discord_emote": [(128, 128)]}
EXACT = {"twitch_banner": (1200, 480), "twitch_offline": (1920, 1080), "stream_screen": (1920, 1080),
         "youtube_banner": (2560, 1440), "youtube_thumbnail": (1280, 720)}
ASSETS = (*PACKS, *EXACT, "sticker", "logo", "console_skin", "illustration", "other")
EDGE_MARGIN = 0.04                       # artwork closer than 4% of the canvas to an edge counts as touching it


def _open(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def _png(im: Image.Image) -> bytes:
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return b.getvalue()


def inspect(png: bytes) -> dict:
    """{width, height, transparent, touches_edge}. touches_edge: opaque pixels of a transparent image reach the outer margin."""
    im = _open(png)
    w, h = im.size
    transparent = im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 255
    touches = False
    if transparent:
        box = im.getchannel("A").point(lambda a: 255 if a > 32 else 0).getbbox()
        mx, my = int(w * EDGE_MARGIN), int(h * EDGE_MARGIN)
        touches = bool(box) and (box[0] < mx or box[1] < my or box[2] > w - mx or box[3] > h - my)
    return {"width": w, "height": h, "transparent": transparent, "touches_edge": touches}


def pad(png: bytes, margin: float = 0.06) -> bytes:
    """Shrink the artwork onto a same-size transparent canvas so it has `margin` free space on every side."""
    im = _open(png).convert("RGBA")
    w, h = im.size
    inner = im.resize((int(w * (1 - 2 * margin)), int(h * (1 - 2 * margin))), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(inner, ((w - inner.width) // 2, (h - inner.height) // 2), inner)
    return _png(out)


def fit_exact(png: bytes, width: int, height: int) -> bytes:
    """Centre-crop to the target aspect ratio, then resize: the art director keeps important content in the centre safe area."""
    im = _open(png)
    w, h = im.size
    target = width / height
    if w / h > target:
        cw = int(h * target)
        im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    else:
        ch = int(w / target)
        im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
    return _png(im.resize((width, height), Image.LANCZOS))


def pack(png: bytes, sizes) -> list[tuple[str, bytes]]:
    im = _open(png).convert("RGBA")
    return [(f"{w}x{h}", _png(im.resize((w, h), Image.LANCZOS))) for w, h in sizes]


def size_like(png: bytes) -> str:
    """The generation canvas closest to a reference image's shape (edits keep the source's framing)."""
    w, h = _open(png).size
    return "1536x1024" if w > h * 1.2 else "1024x1536" if h > w * 1.2 else "1024x1024"
