# -*- coding: utf-8 -*-
"""Convert optional AFY WOFF/WOFF2 fonts to TTF before build.
No font files are bundled by default. Put licensed font files in assets/fonts.
"""
from pathlib import Path

def main() -> int:
    fonts_dir = Path('assets/fonts')
    fonts_dir.mkdir(parents=True, exist_ok=True)
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        print('fontTools not installed; skipping font conversion')
        return 0
    for name in ['AFYRegular', 'AFYBold']:
        out = fonts_dir / f'{name}.ttf'
        if out.exists():
            print(f'{out} already exists')
            continue
        for ext in ['woff2', 'woff']:
            src = fonts_dir / f'{name}.{ext}'
            if src.exists():
                try:
                    font = TTFont(str(src))
                    font.flavor = None
                    font.save(str(out))
                    print(f'Converted {src} -> {out}')
                    break
                except Exception as exc:
                    print(f'Could not convert {src}: {exc}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
