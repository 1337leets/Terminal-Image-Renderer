#!/usr/bin/env python3
# main_app.py  (Textual uyumluluk: ScrollView mount ile safe, ctrl+q quits)

import os
import shutil
import asyncio
from typing import List, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Static, Input
# ScrollView import denemeleri; fallback ver
try:
    from textual.widgets.scroll_view import ScrollView  # type: ignore
except Exception:
    try:
        from textual.widgets import ScrollView  # type: ignore
    except Exception:
        class ScrollView(Static):  # type: ignore
            async def scroll_end(self, animate: bool = False) -> None:
                return

from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual import events

# import pixel canvas helpers
try:
    from pixel_renderer import PixelCanvas, image_to_canvas, DEFAULT_FONT_PX, H_SCALE, BG_COLOR
except Exception as e:
    raise SystemExit(f"Missing or broken pixel_renderer.py: {e}")

ASSETS_IMAGE = os.path.join("assets", "ss.jpg")
LEFT_FRAC = 0.30
MARGIN_ROWS = 4

class CanvasWidget(Static):
    canvas: PixelCanvas | None = None
    def set_canvas(self, canvas: PixelCanvas):
        self.canvas = canvas
        self.refresh_view()
    def refresh_view(self):
        if not self.canvas:
            self.update("")
            return
        lines = self.canvas.to_rich_lines(h_scale=H_SCALE)
        self.update("\n".join(lines))

class MainApp(App):
    CSS = """
    Screen { background: black; color: white; }
    #leftcol { width: 30%; border: solid green; padding: 1 1; }
    #rightcol { border: solid cyan; padding: 0 0; overflow: auto; }
    #bottom { height: 1; background: gray; color: white; padding: 0 1; dock: bottom; }
    """

    # ONLY ctrl+q quits (so ctrl+c remains terminal copy)
    BINDINGS = [
        ("ctrl+q", "quit", "Quit"),
    ]

    status: reactive[str] = reactive("Ready")

    def compose(self) -> ComposeResult:
        self.log_static = Static("", id="log_static", markup=True)
        self.log_scroll = ScrollView(id="log_scroll")
        self.input_widget = Input(placeholder="Type text and press Enter (or press i to render image)", id="left_input")
        self.canvas_widget = CanvasWidget("", id="right_canvas")
        self.bottom_static = Static(self.status, id="bottom")
        yield Horizontal(
            Vertical(self.log_scroll, self.input_widget, id="leftcol"),
            Vertical(self.canvas_widget, self.bottom_static, id="rightcol")
        )

    async def on_mount(self) -> None:
        os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
        self.log_lines: List[str] = []
        try:
            await self.log_scroll.mount(self.log_static)
        except Exception:
            try:
                self.log_scroll.update("")
            except Exception:
                pass
        self.log_write("Welcome — left box is log/input. Right box renders bitmap canvas.")
        self.log_write("Type text in the input and press Enter to render it as bitmap.")
        self.log_write("Press 'i' (while focused anywhere) to render assets/ss.jpg into canvas.")
        cols, rows = shutil.get_terminal_size((80, 24))
        canvas_w = max(4, (cols - int(cols * LEFT_FRAC) - 4) // H_SCALE)
        canvas_h = max(4, rows - MARGIN_ROWS)
        self.canvas = PixelCanvas(canvas_w, canvas_h)
        self.canvas.clear()
        self.canvas_widget.set_canvas(self.canvas)
        self.set_status(f"Canvas {canvas_w}×{canvas_h} px")

    def log_write(self, text: str) -> None:
        self.log_lines.append(text)
        try:
            self.log_static.update("\n".join(self.log_lines))
        except Exception:
            try:
                self.log_scroll.update("\n".join(self.log_lines))
            except Exception:
                pass
        try:
            asyncio.create_task(self.log_scroll.scroll_end(animate=False))
        except Exception:
            pass

    def set_status(self, text: str) -> None:
        self.status = text
        try:
            self.bottom_static.update(self.status)
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            self.input_widget.value = ""
            return
        self.log_write(f"> {text}")
        font_px = max(6, DEFAULT_FONT_PX)
        self.canvas.clear()
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.canvas.stamp_text, text, 0, 0, font_px, (255,255,255), BG_COLOR)
            self.canvas_widget.refresh_view()
            self.set_status(f"Rendered text '{text}'")
        except Exception as e:
            self.log_write(f"[red]Error rendering text: {e}[/red]")
            self.set_status("Error rendering text")
        self.input_widget.value = ""

    async def on_key(self, event: events.Key) -> None:
        # i -> render image; ctrl+q handled by binding
        if event.key == "i":
            await self._render_image_async()

    async def _render_image_async(self):
        cols, rows = shutil.get_terminal_size((80, 24))
        canvas_w = max(4, (cols - int(cols * LEFT_FRAC) - 4) // H_SCALE)
        canvas_h = max(4, rows - MARGIN_ROWS)
        self.set_status("Rendering image...")
        loop = asyncio.get_running_loop()
        try:
            new_canvas = await loop.run_in_executor(None, image_to_canvas, ASSETS_IMAGE, canvas_w, canvas_h)
            self.canvas = new_canvas
            self.canvas_widget.set_canvas(self.canvas)
            self.set_status(f"Rendered image {canvas_w}×{canvas_h}")
            self.log_write(f"[green]Image rendered to canvas {canvas_w}×{canvas_h}[/green]")
        except Exception as e:
            self.log_write(f"[red]Image render error: {e}[/red]")
            self.set_status("Image error")

    async def on_resize(self, event: events.Resize) -> None:
        await asyncio.sleep(0.06)
        cols, rows = shutil.get_terminal_size((80, 24))
        canvas_w = max(4, (cols - int(cols * LEFT_FRAC) - 4) // H_SCALE)
        canvas_h = max(4, rows - MARGIN_ROWS)
        old = getattr(self, "canvas", None)
        new_canvas = PixelCanvas(canvas_w, canvas_h)
        new_canvas.clear()
        if old:
            for y in range(min(old.h, new_canvas.h)):
                for x in range(min(old.w, new_canvas.w)):
                    new_canvas.pixels[y][x] = old.pixels[y][x]
        self.canvas = new_canvas
        self.canvas_widget.set_canvas(self.canvas)
        self.set_status(f"Canvas resized {canvas_w}×{canvas_h}")

    def action_quit(self) -> None:
        self.exit()

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    MainApp().run()
