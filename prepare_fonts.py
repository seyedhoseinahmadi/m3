# -*- coding: utf-8 -*-
"""
Prepare AFY fonts for HiMate Sync build.

This script does not include or download any font.
If licensed font files are provided by project owner in assets/fonts as WOFF/WOFF2,
it tries to convert them to TTF so Windows/Tkinter can load them.

Input examples:
- assets/fonts/AFYRegular.woff2
- assets/fonts/AFYBold.woff2

Output examples:
- assets/fonts/AFYRegular.ttf
- assets/fonts/AFYBold.ttf
"""

from pathlib import Path

FONTS_DIR = Path("assets") / "fonts"


def main() -> int:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        print("fontTools is not available; skipping font conversion.")
        return 0

    converted = 0
    for src in list(FONTS_DIR.glob("*.woff")) + list(FONTS_DIR.glob("*.woff2")):
        out = src.with_suffix(".ttf")
        if out.exists():
            continue
        try:
            font = TTFont(str(src))
            font.flavor = None
            font.save(str(out))
            print(f"Converted {src} -> {out}")
            converted += 1
        except Exception as exc:
            print(f"Could not convert {src}: {exc}")

    print(f"Font conversion done. Converted: {converted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
