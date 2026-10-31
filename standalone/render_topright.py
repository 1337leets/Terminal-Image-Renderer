#!/usr/bin/env python3
"""
render_topright.py

Render an image in the top-right corner of the current terminal as a small "pixel box".
- Each image pixel -> two full-block characters "██".
- Uses adaptive 256-color quantization (fast) by default to reduce ANSI churn.
- Chunked, run-length optimized output for speed.
- Default image: "ss.jpg" in the current folder (or pass path as argv).
- Place small box at top-right (doesn't redraw full terminal).
Usage:
    python3 render_topright.py [image_path] [--box-px-w N] [--box-px-h N] [--no-color]
Examples:
    python3 render_topright.py ss.jpg
    python3 render_topright.py ss.jpg --box-px-w 32 --box-px-h 32
"""

from __future__ import annotations
import sys
import os
import shutil
import argparse
from typing import List, Tuple, Optional
from PIL import Image, ImageOps

ESC = "\x1b["
SAVE_CURSOR = ESC + "s"
RESTORE_CURSOR = ESC + "u"
HIDE_CURSOR = ESC + "?25l"
SHOW_CURSOR = ESC + "?25h"

def term_size() -> Tuple[int,int]:
    cols, rows = shutil.get_terminal_size((80, 24))
    return cols, rows

def set_fg_rgb(r:int,g:int,b:int) -> str:
    return f"{ESC}38;2;{r};{g};{b}m"

def reset_all() -> str:
    return f"{ESC}0m"

def move_cursor(row:int, col:int) -> str:
    return f"{ESC}{row};{col}H"

def load_image(path: str) -> Image.Image:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")
    img = Image.open(path)
    return img.convert("RGB")

def quantize_palette(img: Image.Image, colors: int = 256) -> Tuple[Image.Image, List[Tuple[int,int,int]]]:
    """
    Convert to P mode with adaptive palette and return (p_img, palette_list)
    palette_list is list of (r,g,b) length 256
    """
    p = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
    pal = p.getpalette() or []
    # pad to 256*3
    if len(pal) < 768:
        pal = pal + [0] * (768 - len(pal))
    palette = [tuple(pal[i:i+3]) for i in range(0, 768, 3)]
    return p, palette

def build_row_runs_from_p(p_img: Image.Image, palette: List[Tuple[int,int,int]], y: int) -> str:
    """
    Build a single text row for pixel-row y (each pixel -> '██').
    Uses run-length grouping of identical palette indices to minimize ANSI escapes.
    """
    w, h = p_img.size
    # convert to list so slicing/indexing is reliable across PIL versions
    data = list(p_img.getdata())
    start = y * w
    row_indexes = data[start:start+w]
    out_parts: List[str] = []
    x = 0
    while x < w:
        idx = row_indexes[x]
        r,g,b = palette[idx]
        # run length
        run = 1
        x2 = x + 1
        while x2 < w and row_indexes[x2] == idx:
            run += 1
            x2 += 1
        # emit color once, write run times "██", then reset
        out_parts.append(set_fg_rgb(r,g,b))
        out_parts.append("██" * run)
        out_parts.append(reset_all())
        x = x2
    return "".join(out_parts)

def build_row_runs_rgb(pixels, w, y) -> str:
    """
    Alternative: if not quantizing, build using exact RGB. pixels should be PixelAccess or list.
    This function won't be used when quantized, kept for reference.
    """
    out_parts: List[str] = []
    x = 0
    while x < w:
        r,g,b = pixels[x,y]
        run = 1
        x2 = x + 1
        while x2 < w:
            nr,ng,nb = pixels[x2,y]
            if nr==r and ng==g and nb==b:
                run += 1
                x2 += 1
            else:
                break
        out_parts.append(set_fg_rgb(r,g,b))
        out_parts.append("██" * run)
        out_parts.append(reset_all())
        x = x2
    return "".join(out_parts)

def render_to_topright(image_path: str, box_px_w: Optional[int], box_px_h: Optional[int], no_color: bool = False, quantize: bool = True):
    cols, rows = term_size()  # cols chars, rows lines
    # effective pixel area width in pixels (each pixel -> 2 chars)
    max_pixel_w_by_cols = max(1, (cols - 2) // 2)  # leave 2-char margin
    max_pixel_h_by_rows = max(1, rows - 2)         # leave 2-row margin

    # choose defaults if None (try square)
    if box_px_w is None and box_px_h is None:
        # default square: keep small relative to terminal; user said 50x75 terminal
        default_px = min( min(32, max_pixel_w_by_cols), max_pixel_h_by_rows )
        box_w = default_px
        box_h = default_px
    elif box_px_w is None:
        box_h = min(box_px_h, max_pixel_h_by_rows)
        box_w = min(box_h, max_pixel_w_by_cols)
    elif box_px_h is None:
        box_w = min(box_px_w, max_pixel_w_by_cols)
        box_h = min(box_w, max_pixel_h_by_rows)
    else:
        box_w = min(box_px_w, max_pixel_w_by_cols)
        box_h = min(box_px_h, max_pixel_h_by_rows)

    # Load image
    img = load_image(image_path)

    # compute target dims preserving aspect ratio, but don't exceed box
    iw, ih = img.size
    ratio = min(box_w / iw, box_h / ih, 1.0)
    target_w = max(1, int(iw * ratio))
    target_h = max(1, int(ih * ratio))

    # Final pixel grid size (target_w x target_h)
    resized = img.resize((target_w, target_h), resample=Image.NEAREST)

    # Optionally quantize to reduce color variety (faster output)
    if quantize and not no_color:
        p_img, palette = quantize_palette(resized, colors=256)
    else:
        # convert resized to direct RGB pixel access if not quantize
        p_img = None
        palette = None
        pix = resized.load()

    # compute left padding in characters so box ends at right edge
    used_char_cols = target_w * 2
    left_padding = max(0, cols - used_char_cols + 1)  # +1 to nudge into right side
    pad_str = " " * left_padding

    out = sys.stdout
    write = out.write

    # Save cursor and hide cursor
    write(SAVE_CURSOR)
    write(HIDE_CURSOR)

    try:
        # Move to first row of box (top row = 1)
        start_row = 1
        # We'll write each pixel-row at (row=start_row + y, col=left_padding+1)
        for y in range(target_h):
            row_str = ""
            if palette:
                # using quantized palette
                row_str = build_row_runs_from_p(p_img, palette, y)
            else:
                # build from exact rgb pixels
                parts: List[str] = []
                x = 0
                while x < target_w:
                    r,g,b = pix[x,y]
                    # run-length
                    run = 1
                    x2 = x + 1
                    while x2 < target_w:
                        nr,ng,nb = pix[x2,y]
                        if nr==r and ng==g and nb==b:
                            run += 1
                            x2 += 1
                        else:
                            break
                    if no_color:
                        # threshold luminance
                        lum = (r*299 + g*587 + b*114) // 1000
                        if lum < 128:
                            parts.append("██" * run)
                        else:
                            parts.append("  " * run)
                    else:
                        parts.append(set_fg_rgb(r,g,b))
                        parts.append("██" * run)
                        parts.append(reset_all())
                    x = x2
                row_str = "".join(parts)
            # final full line = move cursor + pad + row_str
            write(move_cursor(start_row + y, left_padding + 1))
            write(pad_str)  # ensure start column (some terminals need)
            write(row_str)
            # small flush per row to allow progressive drawing (fast)
            out.flush()
        # done; move cursor below box (or restore)
        write(RESTORE_CURSOR)
        write(SHOW_CURSOR)
        out.flush()
    except BrokenPipeError:
        # terminal closed / piped away; exit silently
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    except KeyboardInterrupt:
        # restore cursor and exit
        write(RESTORE_CURSOR)
        write(SHOW_CURSOR)
        out.flush()
        raise
    finally:
        # ensure reset and cursor visible
        try:
            write(reset_all())
            write(SHOW_CURSOR)
            write(RESTORE_CURSOR)
            out.flush()
        except Exception:
            pass

def main():
    p = argparse.ArgumentParser(description="Render image top-right as compact pixel box (each pixel -> '██').")
    p.add_argument("image", nargs="?", default="ss.jpg", help="path to image (default ss.jpg)")
    p.add_argument("--box-px-w", type=int, default=None, help="box width in image pixels")
    p.add_argument("--box-px-h", type=int, default=None, help="box height in image pixels")
    p.add_argument("--no-color", action="store_true", help="render in black/white blocks only")
    p.add_argument("--no-quantize", action="store_true", help="disable 256-color quantization (may be slower)")
    args = p.parse_args()

    img_path = args.image
    no_color = args.no_color
    quantize = not args.no_quantize

    try:
        render_to_topright(img_path, args.box_px_w, args.box_px_h, no_color=no_color, quantize=quantize)
    except Exception as e:
        sys.stderr.write("ERROR: " + str(e) + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
