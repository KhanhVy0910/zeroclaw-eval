import subprocess
from pathlib import Path

edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
fig_dir = Path("docs/figures")
png_dir = Path("docs/figures/png")
png_dir.mkdir(parents=True, exist_ok=True)

for svg_file in sorted(fig_dir.glob("D*.svg")):
    name = svg_file.stem
    html_file = png_dir / f"{name}.html"
    png_file = png_dir / f"{name}.png"
    
    html_content = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 20px; background: #ffffff; display: flex; justify-content: center; align-items: center; }}
  svg {{ max-width: 1000px; height: auto; }}
</style>
</head>
<body>
{svg_file.read_text(encoding="utf-8")}
</body>
</html>'''
    html_file.write_text(html_content, encoding="utf-8")
    
    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        f"--screenshot={png_file.resolve()}",
        "--window-size=1040,600",
        str(html_file.resolve())
    ]
    res = subprocess.run(cmd, capture_output=True)
    if png_file.exists():
        print(f"Rendered {name} -> {png_file.name} ({png_file.stat().st_size} bytes)")
    else:
        print(f"Failed to render {name}: {res.stderr}")
