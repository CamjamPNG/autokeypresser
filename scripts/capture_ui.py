import time
import os
from pathlib import Path

import tkinter as tk
from PIL import ImageGrab

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autoclicker.app import AutoClickerApp

out = Path(__file__).resolve().parent.parent / "img"
out.mkdir(exist_ok=True)

root = tk.Tk()
app = AutoClickerApp(root)
app._apply_theme(os.environ.get("AKP_SCREENSHOT_THEME", "Aurora"))
root.update()
root.lift()
root.attributes("-topmost", True)
root.focus_force()
root.update()

time.sleep(2.0)
root.update()

x, y = root.winfo_rootx(), root.winfo_rooty()
w, h = root.winfo_width(), root.winfo_height()
img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
img.save(out / "example.png")
print("saved", out / "example.png", img.size)

time.sleep(2.0)
root.destroy()
