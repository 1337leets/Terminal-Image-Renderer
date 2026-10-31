# Terminal Image Renderer

Draws images in a terminal using colored full-block characters, inside a [Textual](https://github.com/Textualize/textual) interface.

This started as the rendering side of a text-based game. The game itself was never built, so what remains is the renderer and a small two-column demo app.

## How It Works

The image is resized with nearest-neighbor sampling, keeping its aspect ratio, and placed on a pixel canvas. Each pixel becomes `██`, two full-block characters in 24-bit color, because a terminal cell is about twice as tall as it is wide. Neighboring pixels of the same color on a row are merged into one styled run to keep the output small.

The image size is limited by `BOX_PIXELS` in `terminal_image_viewer.py`, which is 24 by default. Each pixel takes two columns, so higher values need a large terminal or a smaller font.

## Files

| File | Content |
|------|---------|
| `pixel_renderer.py` | The canvas and the conversion from an image to colored text |
| `terminal_image_viewer.py` | The demo app, which shows `assets/ss.jpg` at the top right |
| `run_with_small_font_ps.py` | Windows wrapper that shrinks the console font for more detail and restores it on exit |
| `console_font.py` | Console font calls used by the wrapper |

## Usage

```
pip install -r requirements.txt
python terminal_image_viewer.py
```

Ctrl+Q quits. For more detail in the Windows console:

```
python run_with_small_font_ps.py terminal_image_viewer.py
```

The input box on the left is a leftover from the game idea and does not do anything yet.

## Standalone Scripts

`standalone/` holds three earlier scripts I wrote on my phone. They use the same `██` pixels but need only Pillow, not Textual, and they write straight to the terminal.

| File | Content |
|------|---------|
| `render_image.py` | Clears the screen and draws an image at a chosen width and height, with `--no-color` for black and white |
| `render_topright.py` | Draws a small image in the top right corner of the current terminal without redrawing the rest |
| `launch_kitty.py` | Opens a kitty window with a chosen font size and runs `render_image.py` in it, which needs kitty |

```
python standalone/render_image.py assets/ss.jpg --width 40
python standalone/render_topright.py assets/ss.jpg --box-px-w 32 --box-px-h 32
python standalone/launch_kitty.py assets/ss.jpg --font-size 6
```

## License

MIT
