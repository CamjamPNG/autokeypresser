from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent.parent
out = root / "img"
out.mkdir(exist_ok=True)

W, H = 720, 180
img = Image.new("RGB", (W, H), "#ececec")
draw = ImageDraw.Draw(img)

draw.rectangle([0, H - 8, W, H], fill="#d03c3c")

fonts = [
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
bold = next((f for f in fonts if f.exists()), None)

title_font = ImageFont.truetype(str(bold), 64) if bold else ImageFont.load_default()
sub_font = ImageFont.truetype(str(bold), 26) if bold else ImageFont.load_default()

title = "AutoKeyPresser 1.1"
sub = "Cross-platform auto presser - keyboard & mouse"

tw = draw.textlength(title, font=title_font)
sw = draw.textlength(sub, font=sub_font)
draw.text(((W - tw) / 2, 26), title, fill="#222222", font=title_font)
draw.text(((W - sw) / 2, 116), sub, fill="#555555", font=sub_font)

img.save(out / "banner.png")
print("saved", out / "banner.png")
