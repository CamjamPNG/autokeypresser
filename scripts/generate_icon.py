from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parent.parent
out = root / "img"
out.mkdir(exist_ok=True)

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

draw.rounded_rectangle(
    [0, 0, SIZE - 1, SIZE - 1], radius=48, fill=(46, 46, 48, 255)
)
draw.rounded_rectangle(
    [8, 8, SIZE - 9, SIZE - 9], radius=42, outline=(208, 60, 60, 255), width=6
)

# mouse cursor arrow
ax, ay = 76, 70
pts = [(ax, ay), (ax, ay + 96), (ax + 34, ay + 74), (ax + 62, ay + 118), (ax + 84, ay + 106), (ax + 54, ay + 62)]
draw.polygon(pts, fill=(238, 238, 238, 255))
draw.line([(ax + 34, ay + 74), (ax + 54, ay + 62)], fill=(46, 46, 48, 255), width=5)

# click ripple rings (top-right)
cx, cy = 190, 80
for r, col in ((38, (208, 60, 60, 255)), (62, (208, 60, 60, 200))):
    bbox = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(bbox, outline=col, width=7)

img.save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("saved", out / "icon.png", out / "icon.ico")
