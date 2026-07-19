# -*- coding: utf-8 -*-
"""
Prepare licensed AFY/IRANYekanWeb fonts for the HiMate Windows build.

Expected source files in assets/fonts:
- AFYRegular.woff2 or AFYRegular.woff
- AFYBold.woff2 or AFYBold.woff

Generated Windows font files:
- AFYRegular.ttf
- AFYBold.ttf

The actual family name inside the supplied fonts is IRANYekanWeb.
"""

from pathlib import Path
import sys

FONTS_DIR = Path("assets") / "fonts"
REQUIRED = {
    "AFYRegular.ttf": ["AFYRegular.woff2", "AFYRegular.woff"],
    "AFYBold.ttf": ["AFYBold.woff2", "AFYBold.woff"],
}


def convert_font(src: Path, out: Path) -> None:
    from fontTools.ttLib import TTFont

    font = TTFont(str(src))
    font.flavor = None
    font.save(str(out))


def main() -> int:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        import fontTools  # noqa: F401
    except Exception as exc:
        print(f"ERROR: fontTools is not available: {exc}")
        return 1

    missing_sources = []
    for output_name, candidates in REQUIRED.items():
        source = next((FONTS_DIR / name for name in candidates if (FONTS_DIR / name).exists()), None)
        if source is None:
            missing_sources.append(" or ".join(candidates))
            continue

        output = FONTS_DIR / output_name
        try:
            if output.exists():
                output.unlink()
            convert_font(source, output)
            print(f"Converted {source} -> {output}")
        except Exception as exc:
            print(f"ERROR: Could not convert {source}: {exc}")
            return 1

    if missing_sources:
        print("ERROR: Required licensed font source files are missing:")
        for item in missing_sources:
            print(f" - {item}")
        return 1

    missing_outputs = [name for name in REQUIRED if not (FONTS_DIR / name).exists()]
    if missing_outputs:
        print("ERROR: Font conversion did not create:")
        for name in missing_outputs:
            print(f" - assets/fonts/{name}")
        return 1

    print("Font preparation completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
