# pixel_renderer.py
from __future__ import annotations
import os
from typing import Tuple, List, Optional
from PIL import Image, ImageOps
from rich.text import Text

BG_COLOR = (0,0,0)
MAX_PIXEL_BOX = 256   # yüksek denemeler için; ihtiyaca göre düşür

class PixelCanvas:
    def __init__(self, w:int, h:int, bg:Tuple[int,int,int]=BG_COLOR):
        self.w = max(1, w)
        self.h = max(1, h)
        self.bg = bg
        self.pixels: List[List[Tuple[int,int,int]]] = [
            [bg for _ in range(self.w)] for _ in range(self.h)
        ]

    def clear(self, color:Optional[Tuple[int,int,int]] = None):
        c = color if color is not None else self.bg
        for y in range(self.h):
            for x in range(self.w):
                self.pixels[y][x] = c

    def stamp_image(self, pil_img:Image.Image, dest_x:int=0, dest_y:int=0):
        img = pil_img.convert("RGB")
        iw, ih = img.size
        pix = img.load()
        for yy in range(ih):
            dy = dest_y + yy
            if dy < 0 or dy >= self.h: continue
            for xx in range(iw):
                dx = dest_x + xx
                if dx < 0 or dx >= self.w: continue
                self.pixels[dy][dx] = pix[xx, yy]

    def to_rich_text_lines_fullblock(self) -> List[Text]:
        """
        Return list of Rich Text objects. Each pixel -> '██' (two full block chars).
        Each Text.plain length should equal self.w * 2.
        """
        lines: List[Text] = []
        for y in range(self.h):
            row = self.pixels[y]
            tline = Text(no_wrap=True)
            x = 0
            # run-length grouping by identical RGB values
            while x < self.w:
                r,g,b = row[x]
                run = 1
                x2 = x + 1
                while x2 < self.w and row[x2] == (r,g,b):
                    run += 1
                    x2 += 1
                # emit colored segment: '██' * run
                seg = Text("██" * run, style=f"rgb({r},{g},{b})", no_wrap=True)
                tline.append(seg)
                x = x2
            # pad to exact width if somehow shorter
            expected = self.w * 2
            if len(tline.plain) < expected:
                tline.append(Text(" " * (expected - len(tline.plain)), no_wrap=True))
            lines.append(tline)
        return lines

def image_to_canvas_contain(img_path:str, canvas_w:int, canvas_h:int) -> PixelCanvas:
    """
    Resize image to fit inside canvas (contain) preserving aspect ratio, center it, NEAREST resample.
    """
    if not os.path.exists(img_path):
        raise FileNotFoundError(img_path)
    img = Image.open(img_path).convert("RGB")
    resized = ImageOps.contain(img, (canvas_w, canvas_h), method=Image.NEAREST)
    c = PixelCanvas(canvas_w, canvas_h)
    c.clear()
    rx, ry = resized.size
    off_x = max(0, (canvas_w - rx)//2)
    off_y = max(0, (canvas_h - ry)//2)
    c.stamp_image(resized, off_x, off_y)
    return c

def image_to_canvas_exact(img_path:str, canvas_w:int, canvas_h:int) -> PixelCanvas:
    """
    Resize image to EXACT canvas_w x canvas_h using NEAREST (stretches if needed).
    """
    if not os.path.exists(img_path):
        raise FileNotFoundError(img_path)
    img = Image.open(img_path).convert("RGB")
    resized = img.resize((canvas_w, canvas_h), resample=Image.NEAREST)
    c = PixelCanvas(canvas_w, canvas_h)
    c.clear()
    c.stamp_image(resized, 0, 0)
    return c
