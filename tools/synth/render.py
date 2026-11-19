"""Render visa.html files to PNG and add phone-camera noise (for testing the document reader).

pip install playwright opencv-python-headless && playwright install chromium
python tools/synth/render.py --dir data/synthetic --noise

The noise is a small OpenCV/numpy pipeline (tilt, perspective, uneven light,
blur, sensor noise, JPEG compression). It replaced Augraphy, whose default
pipeline crashes with recent numpy versions.
"""
import argparse
from pathlib import Path


def camera_noise(img, rng):
    """Make a clean screenshot look like a quick phone photo of a paper document."""
    import cv2
    import numpy as np

    h, w = img.shape[:2]
    # Paper on a darker table: pad with a background colour.
    pad = int(0.08 * max(h, w))
    bg = [int(x) for x in rng.integers(60, 140, size=3)]
    img = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=bg)
    h, w = img.shape[:2]

    # Slight perspective tilt (camera not parallel to the page).
    j = 0.04 * min(h, w)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-j, j, size=src.shape).astype(np.float32)
    m = cv2.getPerspectiveTransform(src, dst)
    img = cv2.warpPerspective(img, m, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # Small rotation.
    angle = float(rng.uniform(-3, 3))
    r = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    img = cv2.warpAffine(img, r, (w, h), borderMode=cv2.BORDER_REPLICATE)

    # Uneven lighting: a soft gradient across the page.
    f = img.astype(np.float32)
    gx = np.linspace(rng.uniform(0.75, 1.0), rng.uniform(0.95, 1.1), w, dtype=np.float32)
    gy = np.linspace(rng.uniform(0.85, 1.05), rng.uniform(0.8, 1.0), h, dtype=np.float32)
    f *= np.outer(gy, gx)[..., None]

    # Warm/cool colour cast and sensor noise.
    f *= rng.uniform(0.92, 1.08, size=3).astype(np.float32)
    f += rng.normal(0, rng.uniform(3, 9), size=f.shape).astype(np.float32)
    img = np.clip(f, 0, 255).astype(np.uint8)

    # Focus / motion blur.
    k = int(rng.choice([1, 3, 3, 5]))
    if k > 1:
        img = cv2.GaussianBlur(img, (k, k), 0)

    # JPEG compression artefacts (as when sent over WhatsApp).
    q = int(rng.integers(35, 75))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/synthetic")
    ap.add_argument("--noise", action="store_true", help="also write visa_photo.png with camera-style noise")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    files = sorted(Path(a.dir).glob("case_*/visa.html"))
    if not files:
        print(f"No case_*/visa.html files in {a.dir}. Run tools/synth/generate.py first.")
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 860, "height": 560})
        for f in files:
            page.goto(f.resolve().as_uri())
            page.screenshot(path=str(f.with_suffix(".png")))
        browser.close()

    if a.noise:
        import cv2
        import numpy as np

        rng = np.random.default_rng(a.seed)
        for f in files:
            img = cv2.imread(str(f.with_suffix(".png")))
            cv2.imwrite(str(f.with_name("visa_photo.png")), camera_noise(img, rng))
    print(f"Rendered {len(files)} documents" + (" (with photo noise)" if a.noise else ""))


if __name__ == "__main__":
    main()
