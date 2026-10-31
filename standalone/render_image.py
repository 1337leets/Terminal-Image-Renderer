#!/usr/bin/env python3
"""
render_image.py

Fast renderer: image -> terminal using double full-blocks "██" as pixels.
Designed to be run in a dedicated terminal window (kitty recommended).

Usage:
    python3 render_image.py <image_path> [--width N] [--height N] [--no-color] [--hold]

Options:
    --width / -w     : target pixel width (one "pixel" maps to "██" two chars). Default = term_cols//2
    --height / -H    : target pixel height (in pixels). Default = auto by aspect ratio.
    --no-color       : render black/white blocks only (faster).
    --no-quantize    : don't quantize to 256 palette (slower, more escapes).
    --hold / -k      : after drawing, wait for user to press Enter before exit (no prompt).
"""

from __future__ import annotations
import sys
import os
import shutil
import argparse
from typing import Tuple, Optional, List
from PIL import Image, ImageOps

ESC = "\x1b["
CLEAR_SCREEN = ESC + "2J"
MOVE_CURSOR = lambda r, c: f"{ESC}{r};{c}H"
HIDE_CURSOR = ESC + "?25l"
SHOW_CURSOR = ESC + "?25h"
RESET = ESC + "0m"

def term_size() -> Tuple[int,int]:
    cols, rows = shutil.get_terminal_size((80, 24))
    return cols, rows

def load_image(path: str) -> Image.Image:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")
    img = Image.open(path)
    return img.convert("RGB")

def set_fg(r:int,g:int,b:int) -> str:
    return f"{ESC}38;2;{r};{g};{b}m"

def quantize_palette(img, colors=256):
    p = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
    pal = p.getpalette() or []
    if len(pal) < 768:
        pal = pal + [0] * (768 - len(pal))
    palette = [tuple(pal[i:i+3]) for i in range(0, 768, 3)]
    return p, palette

def build_row_from_p(p_img, palette: List[Tuple[int,int,int]], y: int, no_color: bool) -> str:
    w, h = p_img.size
    data = list(p_img.getdata())
    start = y * w
    row = data[start:start+w]
    parts: List[str] = []
    x = 0
    while x < w:
        idx = row[x]
        r,g,b = palette[idx]
        run = 1
        x2 = x + 1
        while x2 < w and row[x2] == idx:
            run += 1
            x2 += 1
        if no_color:
            lum = (r*299 + g*587 + b*114) // 1000
            if lum < 128:
                parts.append("██" * run)
            else:
                parts.append("  " * run)
        else:
            parts.append(set_fg(r,g,b))
            parts.append("██" * run)
            parts.append(RESET)
        x = x2
    return "".join(parts)

def build_row_from_rgb(pixels, w:int, y:int, no_color: bool) -> str:
    parts: List[str] = []
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
        if no_color:
            lum = (r*299 + g*587 + b*114) // 1000
            if lum < 128:
                parts.append("██" * run)
            else:
                parts.append("  " * run)
        else:
            parts.append(set_fg(r,g,b))
            parts.append("██" * run)
            parts.append(RESET)
        x = x2
    return "".join(parts)

def compute_target(img_w:int, img_h:int, target_w_opt:Optional[int], target_h_opt:Optional[int]) -> Tuple[int,int]:
    cols, rows = term_size()
    max_px_w = max(1, cols // 2)   # one "pixel" uses 2 chars
    max_px_h = max(1, rows)
    if target_w_opt is None and target_h_opt is None:
        target_w = min(max_px_w,  min(64, img_w))  # default sensible
        # preserve aspect
        ratio = min(1.0, target_w / img_w)
        target_h = max(1, int(img_h * ratio))
        target_h = min(target_h, max_px_h)
        return target_w, target_h
    if target_w_opt is None:
        h = min(target_h_opt, max_px_h)
        w = max(1, int(img_w * (h / img_h)))
        w = min(w, max_px_w)
        return w, h
    if target_h_opt is None:
        w = min(target_w_opt, max_px_w)
        h = max(1, int(img_h * (w / img_w)))
        h = min(h, max_px_h)
        return w, h
    return min(target_w_opt, max_px_w), min(target_h_opt, max_px_h)

def center_coords_for_box(box_w_pixels:int, box_h_pixels:int) -> Tuple[int,int]:
    cols, rows = term_size()
    used_cols = box_w_pixels * 2
    left = max(1, (cols - used_cols) // 2 + 1)
    top = max(1, (rows - box_h_pixels) // 2 + 1)
    return top, left

def render(image_path: str, target_w:Optional[int], target_h:Optional[int], no_color:bool=False, no_quantize:bool=False, hold:bool=False):
    img = load_image(image_path)
    iw, ih = img.size
    tw, th = compute_target(iw, ih, target_w, target_h)
    # resize
    resized = ImageOps.fit(img, (tw, th), method=Image.NEAREST)

    # choose quantize or direct
    use_quant = (not no_quantize) and (not no_color)
    if use_quant:
        p_img, palette = quantize_palette(resized, colors=256)
    else:
        p_img = None
        palette = None
        pix = resized.load()

    # prepare terminal
    out = sys.stdout
    write = out.write
    write(CLEAR_SCREEN)
    write(HIDE_CURSOR)
    out.flush()

    # center coordinates (top,left)
    top, left = center_coords_for_box(tw, th)

    try:
        for y in range(th):
            # move cursor
            write(MOVE_CURSOR(top + y, left))
            if use_quant:
                line = build_row_from_p(p_img, palette, y, no_color)
            else:
                line = build_row_from_rgb(pix, tw, y, no_color)
            write(line)
            write(RESET)
            out.flush()
    except BrokenPipeError:
        # terminal closed; exit quietly
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
    finally:
        # leave cursor visible, reset attributes
        write(MOVE_CURSOR(top + th + 1, 1))
        write(RESET)
        write(SHOW_CURSOR)
        out.flush()

    if hold:
        # wait for Enter (no prompt)
        try:
            _ = input()
        except Exception:
            pass

def main():
    p = argparse.ArgumentParser()
    p.add_argument("image", help="path to image")
    p.add_argument("--width", "-w", type=int, default=None, help="target pixel width (each pixel -> '██')")
    p.add_argument("--height", "-H", type=int, default=None, help="target pixel height")
    p.add_argument("--no-color", action="store_true", help="black/white only")
    p.add_argument("--no-quantize", action="store_true", help="disable palette quantize")
    p.add_argument("--hold", "-k", action="store_true", help="wait for Enter before exit")
    args = p.parse_args()

    try:
        render(args.image, args.width, args.height, no_color=args.no_color, no_quantize=args.no_quantize, hold=args.hold)
    except Exception as e:
        sys.stderr.write("ERROR: " + str(e) + "\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
