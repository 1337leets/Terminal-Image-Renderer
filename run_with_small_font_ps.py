# run_with_small_font_ps.py
import sys, subprocess, atexit, os
import console_font

if os.name != "nt":
    print("This wrapper is for Windows (conhost / PowerShell). Run app directly on other OSes.")
    sys.exit(1)

if len(sys.argv) < 2:
    print("Usage: python run_with_small_font_ps.py terminal_image_viewer.py [--face Consolas] [--size 1]")
    sys.exit(1)

face = "Consolas"
size = 1
args = sys.argv[1:]
target = args[0]
rest = args[1:]
i = 0
while i < len(rest):
    if rest[i] == "--face" and i+1 < len(rest):
        face = rest[i+1]; i += 2
    elif rest[i] == "--size" and i+1 < len(rest):
        try:
            size = int(rest[i+1])
        except:
            pass
        i += 2
    else:
        i += 1

prev = console_font.set_font_safe(face=face, size_y=size)
if prev is not None:
    print(f"[wrapper] Console font set to {face} size {size} (temporary).")
    atexit.register(console_font.restore_font_safe, prev)
else:
    print("[wrapper] Could not change console font (terminal may ignore this). Continuing anyway.")

py = sys.executable
ret = subprocess.call([py, os.path.abspath(target)])
sys.exit(ret)
