import time
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
root.update()
root.lift()
root.attributes("-topmost", True)
root.focus_force()
root.update()

time.sleep(2.0)
root.update()

x, y = root.winfo_rootx(), root.winfo_rooty()
w, h = root.winfo_width(), root.winfo_height()
img = ImageGrab.grab(bbox=(x - 2, y - 2, x + w + 2, y + h + 2))
img.save(out / "example.png")
print("saved", out / "example.png", img.size)

time.sleep(2.0)
root.destroy()
