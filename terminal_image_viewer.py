# terminal_image_viewer.py
import os
import shutil
import asyncio
from typing import List, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Static, Input
try:
    from textual.widgets.scroll_view import ScrollView  # type: ignore
except Exception:
    try:
        from textual.widgets import ScrollView  # type: ignore
    except Exception:
        class ScrollView(Static):
            async def scroll_end(self, animate: bool = False) -> None:
                return

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from rich.text import Text

from pixel_renderer import PixelCanvas, image_to_canvas_contain, image_to_canvas_exact, MAX_PIXEL_BOX

ASSETS_IMAGE = os.path.join("assets", "ss.jpg")
LEFT_FRAC = 0.30   # width of the left column
MARGIN_ROWS = 1    # row reserved for the status bar

# <-- Change this to control the size of the image box:
BOX_PIXELS = 24    # try 12..48. Each pixel is '██', so the image takes 2*BOX_PIXELS columns.
# -----------------------

class CanvasWidget(Static):
    canvas: PixelCanvas | None = None
    def set_canvas(self, canvas: PixelCanvas):
        self.canvas = canvas
        self.refresh_view()
    def refresh_view(self):
        if not self.canvas:
            self.update("")
            return
        lines = self.canvas.to_rich_text_lines_fullblock()
        # trim empty lines top/bottom
        while lines and lines[0].plain.strip() == "":
            lines.pop(0)
        while lines and lines[-1].plain.strip() == "":
            lines.pop()
        out = Text(no_wrap=False)
        for i, t in enumerate(lines):
            out.append(t)
            if i != len(lines)-1:
                out.append("\n")
        self.update(out)

class AutoRenderApp(App):
    CSS = """
    Screen { background: black; color: white; }
    #leftcol { width: 30%; border: none; padding: 0 0; }
    #rightcol { border: none; padding: 0 0; overflow: auto; }
    #image_box { padding: 0 0; }
    #bottom { height: 1; background: gray; color: white; padding: 0 1; dock: bottom; }
    """
    BINDINGS = [("ctrl+q", "quit", "Quit")]
    status: reactive[str] = reactive("Ready")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.log_lines: List[str] = []

    def compose(self) -> ComposeResult:
        self.log_static = Static("", id="log_static", markup=True)
        self.log_scroll = ScrollView(id="log_scroll")
        self.input_widget = Input(placeholder="Type and press Enter", id="left_input")
        self.image_box = Static("", id="image_box")
        self.canvas_widget = CanvasWidget("", id="right_canvas")
        self.bottom_static = Static(self.status, id="bottom")
        yield Horizontal(
            Vertical(self.log_scroll, self.input_widget, id="leftcol"),
            Vertical(self.image_box, self.canvas_widget, self.bottom_static, id="rightcol")
        )

    async def on_mount(self) -> None:
        os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
        try:
            await self.log_scroll.mount(self.log_static)
        except Exception:
            pass
        self.write_log("Started. Rendering image with FULL-BLOCK method (each pixel -> '██').")
        cols, rows = shutil.get_terminal_size((80, 24))
        # canvas dimensions for the main UI (not the small image box)
        canvas_w = max(8, (cols - int(cols * LEFT_FRAC) - 0) // 2)
        canvas_h = max(8, rows - MARGIN_ROWS)
        self.canvas = PixelCanvas(canvas_w, canvas_h)
        self.canvas.clear()
        self.canvas_widget.set_canvas(self.canvas)
        self.set_status(f"Canvas {canvas_w}×{canvas_h} px")
        await asyncio.sleep(0.02)
        await self.render_image_topright()

    def write_log(self, text: str) -> None:
        self.log_lines.append(text)
        last = "\n".join(self.log_lines[-40:])
        try:
            if hasattr(self, "log_static"):
                self.log_static.update(last)
            elif hasattr(self, "log_scroll"):
                self.log_scroll.update(last)
            try:
                asyncio.create_task(self.log_scroll.scroll_end(animate=False))
            except Exception:
                pass
        except Exception:
            pass

    def set_status(self, text: str) -> None:
        self.status = text
        try:
            if hasattr(self, "bottom_static"):
                self.bottom_static.update(self.status)
        except Exception:
            pass

    def _trim_lines(self, lines: List[Text]) -> List[Text]:
        while lines and lines[0].plain.strip() == "":
            lines.pop(0)
        while lines and lines[-1].plain.strip() == "":
            lines.pop()
        return lines

    def _prepare_fullblock_text_sync(self, src_canvas: PixelCanvas, available_cols:int, right_cols_total:int) -> Tuple[Text,int,int]:
        """
        Build final Text for image_box synchronously (safe to run in executor).
        Each pixel -> '██' so used_char_cols = src_canvas.w * 2
        """
        used_char_cols = src_canvas.w * 2
        src_lines = src_canvas.to_rich_text_lines_fullblock()
        src_lines = self._trim_lines(src_lines)
        if not src_lines:
            raise RuntimeError("Empty image after render")

        left_padding_chars = max(0, available_cols - used_char_cols)
        pad_text = Text(" " * left_padding_chars, no_wrap=True)

        out = Text()
        for i, t in enumerate(src_lines):
            line = Text()
            line.append(pad_text)
            line.append(t)
            # truncate to right_cols_total (prevents wrap)
            line.truncate(right_cols_total, overflow="crop")
            out.append(line)
            if i != len(src_lines)-1:
                out.append("\n")
        return out, used_char_cols, len(src_lines)

    async def render_image_topright(self):
        # terminal size
        cols, rows = shutil.get_terminal_size((80, 24))
        left_cols = int(cols * LEFT_FRAC)
        right_cols_total = max(0, cols - left_cols)
        border_fudge = 2
        available_cols = max(0, right_cols_total - border_fudge)

        # available pixel area (each pixel = 2 chars horizontally)
        available_pixel_w = max(1, available_cols // 2)
        available_pixel_h = max(1, rows - MARGIN_ROWS)  # fullblock uses one terminal row per image row

        # read original image size (if available) and decide target pixel size
        try:
            from PIL import Image
            img = Image.open(ASSETS_IMAGE)
            iw, ih = img.size
            img.close()
        except Exception:
            iw = ih = MAX_PIXEL_BOX

        # Choose target_px: don't upscale; cap by BOX_PIXELS to keep it visually small
        target_px = max(1, min(iw, ih, available_pixel_w, available_pixel_h, BOX_PIXELS, MAX_PIXEL_BOX))

        # prepare main canvas
        canvas_w = max(8, (cols - left_cols - 0) // 2)
        canvas_h = max(8, rows - MARGIN_ROWS)
        self.canvas = PixelCanvas(canvas_w, canvas_h)
        self.canvas.clear()

        self.set_status(f"Rendering image box {target_px}×{target_px} px (fullblock)...")
        loop = asyncio.get_running_loop()
        try:
            # build source canvas in executor (contain to preserve aspect)
            src_canvas = await loop.run_in_executor(None, image_to_canvas_contain, ASSETS_IMAGE, target_px, target_px)
            # build Text in executor synchronously
            out_text, used_char_cols, num_lines = await loop.run_in_executor(None, self._prepare_fullblock_text_sync, src_canvas, available_cols, right_cols_total)
            # atomic update
            if hasattr(self, "image_box"):
                self.image_box.update(out_text)
            if hasattr(self, "canvas_widget"):
                self.canvas_widget.set_canvas(self.canvas)
            self.set_status(f"Rendered {target_px}×{target_px} used_cols={used_char_cols}")
            self.write_log(f"DBG: target_px={target_px} used_cols={used_char_cols} avail_cols={available_cols} right_total={right_cols_total} lines={num_lines}")
        except Exception as e:
            self.write_log(f"[error] render failed: {e}")
            self.set_status("Image error")

    async def on_resize(self, event):
        await asyncio.sleep(0.06)
        cols, rows = shutil.get_terminal_size((80, 24))
        left_cols = int(cols * LEFT_FRAC)
        canvas_w = max(8, (cols - left_cols - 0) // 2)
        canvas_h = max(8, rows - MARGIN_ROWS)
        old = getattr(self, "canvas", None)
        new_canvas = PixelCanvas(canvas_w, canvas_h)
        new_canvas.clear()
        if old:
            for y in range(min(old.h, new_canvas.h)):
                for x in range(min(old.w, new_canvas.w)):
                    new_canvas.pixels[y][x] = old.pixels[y][x]
        self.canvas = new_canvas
        if hasattr(self, "canvas_widget"):
            self.canvas_widget.set_canvas(self.canvas)
        await self.render_image_topright()
        self.set_status(f"Canvas resized {canvas_w}×{canvas_h}")

    def action_quit(self) -> None:
        self.exit()

if __name__ == "__main__":
    AutoRenderApp().run()
