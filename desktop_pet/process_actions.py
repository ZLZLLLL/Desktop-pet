"""
Process the 蜡笔小新 action images using flood-fill background detection.
This is much more robust than color thresholds.
"""
from PIL import Image
import numpy as np
from pathlib import Path
from collections import deque

ASSETS_DIR = Path(__file__).parent / "assets"
IMAGE_DIR  = Path(__file__).parent.parent / "image"

BG_THRESHOLD = 195   # any pixel where all RGB >= this AND close to pure gray → background candidate
BG_GRAY_DIST = 25    # max distance from pure gray (R≈G≈B) to still count as background
BG_MIN_LIGHT = 190   # pixel must be bright enough to be background

# (folder_name, source_prefix, frame_count)
ACTIONS = [
    ("impactball", "Impactball", 4),
    ("kungfu",     "KungFu",    5),
    ("fight",      "Fight monsters", 5),
    ("victory",    "Victory",    4),
]

def is_bg_pixel(r, g, b):
    """Check if a pixel is background: very bright and close to neutral gray."""
    # Must be bright enough
    if r < BG_MIN_LIGHT or g < BG_MIN_LIGHT or b < BG_MIN_LIGHT:
        return False
    # Must be close to gray (R, G, B roughly equal)
    gray_dist = max(abs(int(r) - int(g)), abs(int(g) - int(b)), abs(int(r) - int(b)))
    if gray_dist > BG_GRAY_DIST:
        return False
    return True


def flood_fill_bg(arr: np.ndarray) -> np.ndarray:
    """
    Flood-fill from image edges to mark background pixels.
    Returns alpha channel (0 = transparent, 255 = opaque).
    """
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    queue = deque()

    # Add all edge pixels that look like background as seeds
    for x in range(w):
        for y in [0, h-1]:
            r, g, b = arr[y, x, 0], arr[y, x, 1], arr[y, x, 2]
            if is_bg_pixel(r, g, b):
                visited[y, x] = True
                queue.append((x, y))
    for y in range(h):
        for x in [0, w-1]:
            if not visited[y, x]:
                r, g, b = arr[y, x, 0], arr[y, x, 1], arr[y, x, 2]
                if is_bg_pixel(r, g, b):
                    visited[y, x] = True
                    queue.append((x, y))

    # Flood fill: spread to neighbors that also look like background
    while queue:
        x, y = queue.popleft()

        for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                nr, ng, nb = arr[ny, nx, 0], arr[ny, nx, 1], arr[ny, nx, 2]
                if is_bg_pixel(nr, ng, nb):
                    visited[ny, nx] = True
                    queue.append((nx, ny))

    # visited == True means background → transparent (alpha=0)
    # visited == False means foreground → opaque (alpha=255)
    return np.where(visited, 0, 255).astype(np.uint8)


def remove_background(img: Image.Image) -> Image.Image:
    """Remove background using flood-fill and return RGBA image."""
    arr = np.array(img.convert("RGBA"), dtype=np.uint32)
    alpha = flood_fill_bg(arr)
    arr[:, :, 3] = alpha
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def main():
    for folder_name, prefix, frame_count in ACTIONS:
        out_dir = ASSETS_DIR / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        for i in range(1, frame_count + 1):
            src_name = f"{prefix}{i:03d}.jpg"
            src_path = IMAGE_DIR / src_name

            if not src_path.exists():
                print(f"  [WARN] Not found: {src_path}")
                continue

            img = Image.open(src_path)
            img_rgba = remove_background(img)

            dst_name = f"{i:04d}.png"
            dst_path = out_dir / dst_name
            img_rgba.save(dst_path)

            arr = np.array(img_rgba)
            opaque = (arr[:,:,3] > 0).sum()
            total  = arr.shape[0] * arr.shape[1]
            # Check corners are transparent
            corner_check = arr[:20, :20, 3].mean()
            print(f"  {src_name} → {folder_name}/{dst_name}  corner_alpha_avg={corner_check:.1f}  opaque={opaque}/{total} ({opaque/total*100:.1f}%)")

    print("\nDone!")


if __name__ == "__main__":
    main()
