"""Generate application icon for Agent Guru."""
from PIL import Image, ImageDraw, ImageFont
import os

sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
images = []

for size in sizes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size[0] // 2, size[1] // 2
    r = min(cx, cy) - 1
    for i in range(r, 0, -1):
        ratio = i / r
        red = int(100 * ratio + 30)
        green = int(50 * ratio + 20)
        blue = int(200 * ratio + 55)
        draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=(red, green, blue, 255))

    font_size = int(size[0] * 0.6)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "G", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size[0] - tw) // 2
    ty = (size[1] - th) // 2 - bbox[1]
    draw.text((tx, ty), "G", fill=(255, 255, 255, 255), font=font)
    images.append(img)

os.makedirs("assets", exist_ok=True)
images[0].save(
    "assets/icon.ico",
    format="ICO",
    sizes=[(s[0], s[1]) for s in sizes],
    append_images=images[1:],
)
icon_size = os.path.getsize("assets/icon.ico")
print(f"Icon created: assets/icon.ico ({icon_size} bytes)")
