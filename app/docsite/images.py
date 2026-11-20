"""Team photos: one uniform size and framing, no hidden metadata."""
from __future__ import annotations

import base64
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

SIZE = (300, 400)  # passport-photo ratio 3:4, shown at about 150 x 200 px (2x for sharp screens)
MAX_UPLOAD = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


def avatar_data_uri(data: bytes) -> str:
    """Any phone photo -> 300x400 WebP (3:4, like a passport photo), face-friendly crop, EXIF removed."""
    if len(data) > MAX_UPLOAD:
        raise ValueError("The photo is larger than 8 MB.")
    try:
        im = Image.open(BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError("That file is not a photo we can read (use JPG, PNG or WebP).")
    im = ImageOps.exif_transpose(im)  # phone photos are often stored sideways
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (248, 250, 247))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im = ImageOps.fit(im, SIZE, Image.Resampling.LANCZOS, centering=(0.5, 0.35))
    buf = BytesIO()
    im.save(buf, "WEBP", quality=82, method=6)  # a new image: no EXIF, GPS or camera data
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
