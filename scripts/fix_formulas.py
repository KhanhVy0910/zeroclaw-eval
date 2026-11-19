from pathlib import Path

def fix_file(filepath: Path):
    text = filepath.read_text(encoding="utf-8")

    # 1. Replace all double backslashes before LaTeX keywords
    keywords = [
        "frac", "sum", "mathbb", "text", "times", "left", "right",
        "dots", "cdot", "approx", "mathbf", "_", "%", "$"
    ]
    for kw in keywords:
        text = text.replace(f"\\\\{kw}", f"\\{kw}")

    # 2. Fix prose dollar signs in Section 1.3
    text = text.replace(
        "($0.075 / 1M tokens - *đơn giá giả định*)",
        "(0.075 USD / 1M tokens - *đơn giá giả định*)"
    )
    text = text.replace(
        "($0.30 / 1M tokens - *đơn giá giả định*)",
        "(0.30 USD / 1M tokens - *đơn giá giả định*)"
    )
    text = text.replace(
        "$C$: Chi phí tài chính tính bằng USD ($).",
        "$C$: Chi phí tài chính ước tính (USD)."
    )

    # 3. Fix formula in Section 5.4
    target_54_start = "$$C = \\left(\\frac{809,892}"
    target_54_start_single = "$$C = \\left(\\frac{809,892}"
    replacement_54 = r"$$C = \left(\frac{809{,}892}{10^6} \times 0.075\right) + \left(\frac{2{,}774}{10^6} \times 0.30\right) = 0.060742 + 0.000832 \approx 0.061574 \text{ USD}$$"

    # Search and replace line 227
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("$$C =") and ("809,892" in line or "809{,}892" in line):
            lines[i] = "  " + replacement_54
            print(f"Replaced calculation line in {filepath.name} at line {i+1}")

    text = "\n".join(lines)
    filepath.write_text(text, encoding="utf-8")
    print(f"Successfully processed {filepath}")

fix_file(Path("docs/BaoCao.md"))
fix_file(Path("docs/BaoCao_RutGon.md"))
