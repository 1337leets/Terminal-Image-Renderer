#!/usr/bin/env python3
"""
launch_kitty.py

Launch a dedicated kitty window and run render_image.py inside it.
Requires 'kitty' to be installed and available in PATH.

Usage:
    python3 launch_kitty.py <image_path> [--font-size N] [--width N] [--height N] [--hold]

Notes:
 - --font-size controls the kitty font size override; shrink this to make pixels appear more square.
 - The script will pass width/height/hold/no-color args to render_image.py.
"""

from __future__ import annotations
import os
import sys
import shutil
import subprocess
import argparse

def which_or_exit(cmd_name: str):
    path = shutil.which(cmd_name)
    if not path:
        sys.stderr.write(f"ERROR: '{cmd_name}' not found in PATH. Install kitty and retry.\n")
        sys.exit(2)
    return path

def main():
    p = argparse.ArgumentParser()
    p.add_argument("image", help="path to image file")
    p.add_argument("--font-size", "-s", type=int, default=6, help="kitty font_size override (small numbers -> smaller font)")
    p.add_argument("--width", "-w", type=int, default=None, help="target pixel width for renderer")
    p.add_argument("--height", "-H", type=int, default=None, help="target pixel height for renderer")
    p.add_argument("--no-color", action="store_true", help="render black/white only")
    p.add_argument("--hold", action="store_true", help="hold window until Enter pressed in child (useful for inspection)")
    p.add_argument("--render-script", "-r", default="render_image.py", help="renderer script path (default ./render_image.py)")
    args = p.parse_args()

    kitty = which_or_exit("kitty")
    image = os.path.abspath(args.image)
    render_script = os.path.abspath(args.render_script)
    if not os.path.exists(render_script):
        sys.stderr.write(f"ERROR: render script not found: {render_script}\n")
        sys.exit(3)
    if not os.path.exists(image):
        sys.stderr.write(f"WARNING: image not found at: {image} (kitty will open and renderer will error)\n")

    # build renderer args
    child_args = [sys.executable, render_script, image]
    if args.width:
        child_args += ["--width", str(args.width)]
    if args.height:
        child_args += ["--height", str(args.height)]
    if args.no_color:
        child_args += ["--no-color",]
    if args.hold:
        child_args += ["--hold"]

    # Kitty CLI: use --override to set font_size and remove padding for tight pixels
    kitty_cmd = [
        kitty,
        "--title", "ASCII Viewer",
        "--override", f"font_size={args.font_size}",
        "--override", "window_padding_width=0",
        "--override", "window_padding_height=0",
        "bash", "-lc",  # run via shell so the sys.executable can be found in user's env
        " ".join("'" + a.replace("'", "'\"'\"'") + "'" for a in child_args)
    ]

    # Launch
    try:
        subprocess.Popen(kitty_cmd)
        print("Launched kitty with renderer. If pixels look rectangular, try decreasing --font-size (e.g. 5,4,3).")
    except Exception as e:
        sys.stderr.write("Failed to launch kitty: " + str(e) + "\n")
        sys.exit(4)

if __name__ == "__main__":
    main()
