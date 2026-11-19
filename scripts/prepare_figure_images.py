from PIL import Image, ImageChops
from pathlib import Path
import shutil

fig_dir = Path("docs/figures")
png_src = fig_dir / "png"

mapping = [
    (1, "Hinh1", "D6"),
    (2, "Hinh2", "D1"),
    (3, "Hinh3", "D2"),
    (4, "Hinh4", "D7"),
    (5, "Hinh5", "D3"),
    (6, "Hinh6", "D4"),
    (7, "Hinh7", "D5"),
]

for idx, hinh_name, d_name in mapping:
    src_png = png_src / f"{d_name}.png"
    src_svg = fig_dir / f"{d_name}.svg"
    
    # 1. Process PNG: crop margin cleanly with 20px padding
    im = Image.open(src_png)
    bg = Image.new(im.mode, im.size, (255, 255, 255))
    diff = ImageChops.difference(im, bg)
    bbox = diff.getbbox()
    if bbox:
        pad = 20
        crop_box = (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(im.width, bbox[2] + pad),
            min(im.height, bbox[3] + pad),
        )
        im_cropped = im.crop(crop_box)
    else:
        im_cropped = im
        
    dest_png1 = fig_dir / f"{hinh_name}.png"
    dest_png2 = fig_dir / f"{d_name}.png"
    im_cropped.save(dest_png1, "PNG", optimize=True)
    im_cropped.save(dest_png2, "PNG", optimize=True)
    print(f"Saved PNG: {dest_png1.name} & {dest_png2.name} ({im_cropped.size})")

    # 2. Copy SVG to HinhX.svg
    dest_svg = fig_dir / f"{hinh_name}.svg"
    shutil.copy2(src_svg, dest_svg)
    print(f"Copied SVG: {dest_svg.name}")

print("All figure files prepared successfully.")
