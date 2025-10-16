#!/usr/bin/env python3
"""
Compress images in a directory by scaling them to 50% dimensions (width & height),
keeping the same filename and extension, and replacing the originals.

Usage:
  python compress_images_50.py /path/to/images --recursive

Requires:
  pip install pillow
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif"}

def is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in SUPPORTED_EXTS

def compress_image_50_percent(src: Path) -> None:
    """
    Opens the image, applies EXIF orientation, scales to 50% (min 1px),
    and writes back with the same extension via an atomic replace.
    """
    try:
        # Open & normalize orientation
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            # New size is 50% of each dimension (at least 1 px)
            new_w = max(1, w // 2)
            new_h = max(1, h // 2)

            # If already tiny, skip to avoid up/down noise
            if new_w == w and new_h == h:
                return

            im_resized = im.resize((new_w, new_h), resample=Image.LANCZOS)

            # Save to a temp file first
            suffix = src.suffix
            with tempfile.NamedTemporaryFile(delete=False, dir=str(src.parent), suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)

            save_params = {}
            ext = src.suffix.lower()

            # Format-specific save options to keep quality reasonable
            if ext in {".jpg", ".jpeg"}:
                # Keep good quality while benefiting from smaller dimensions
                save_params.update(dict(optimize=True, quality=85, progressive=True))
            elif ext == ".png":
                # For PNG, use optimization; if the image has alpha keep it
                save_params.update(dict(optimize=True))
            elif ext == ".webp":
                # Use a balanced quality for WEBP
                save_params.update(dict(quality=80, method=4))
            elif ext in {".tif", ".tiff"}:
                # Use LZW to keep it lossless but smaller; dimensions do the heavy lifting
                save_params.update(dict(compression="tiff_lzw"))
            elif ext == ".gif":
                # For GIFs, this will handle single-frame GIFs; animated GIFs are skipped below
                pass

            # Skip animated GIFs to avoid breaking animations
            if ext == ".gif" and getattr(im, "is_animated", False):
                # Clean up temp file placeholder if created
                try:
                    if tmp_path.exists():
                        tmp_path.unlink()
                except Exception:
                    pass
                print(f"Skipping animated GIF: {src}", file=sys.stderr)
                return

            # Preserve mode/alpha appropriately
            # Convert paletted images to RGBA/RGB before saving in formats that don't like 'P'
            fmt = None  # let Pillow infer from extension
            mode = im_resized.mode
            if ext in {".jpg", ".jpeg"} and mode not in {"RGB"}:
                im_resized = im_resized.convert("RGB")
            # Save the temp file
            im_resized.save(tmp_path, format=fmt, **save_params)

            # Atomic replace
            tmp_path.replace(src)

    except Exception as e:
        print(f"Error processing {src}: {e}", file=sys.stderr)

def walk_images(root: Path, recursive: bool):
    if recursive:
        for p in root.rglob("*"):
            if is_image_file(p):
                yield p
    else:
        for p in root.iterdir():
            if is_image_file(p):
                yield p

def main():
    parser = argparse.ArgumentParser(description="Compress (scale) all images to 50% and replace in place.")
    parser.add_argument("directory", type=str, nargs="?", default=".", help="Directory containing images (default: current).")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recurse into subdirectories.")
    args = parser.parse_args()

    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        sys.exit(1)

    count = 0
    for img_path in walk_images(root, args.recursive):
        compress_image_50_percent(img_path)
        count += 1

    print(f"Processed {count} image(s) in {root}")

if __name__ == "__main__":
    main()
