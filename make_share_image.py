#!/usr/bin/env python
"""Сайтын линкийг Facebook, Messenger-т хуваалцахад гарах зураг (1200x630): site/img/share.png"""
import os

from PIL import Image, ImageDraw

import make_lesson as M

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    bg = M.make_bg().resize((1200, 675)).crop((0, 22, 1200, 652))
    fr = bg.copy()
    d = ImageDraw.Draw(fr)
    logo = M.watermark_img(3)
    fr.paste(logo, (600 - logo.width // 2, 40), logo)
    M.draw_text_center(d, "Бага ангийн хичээл", 600, 248, 74, (255, 112, 40), stroke=8, stroke_fill=M.C_WHITE)
    tiles = ["а", "э", "м", "+", "1", "2", "3"]
    cell, gap = 104, 16
    x0 = 600 - (len(tiles) * cell + (len(tiles) - 1) * gap) / 2 + cell / 2
    for i, tk in enumerate(tiles):
        M.draw_tile(d, tk, x0 + i * (cell + gap), 380, cell, cell * 1.08, text_size=68,
                    fill=(255, 238, 160) if tk == "+" else M.C_WHITE)
    for x, label, col in ((330, "Монгол хэл", (33, 140, 230)), (870, "Математик", (67, 170, 80))):
        d.rounded_rectangle([x - 190, 470, x + 190, 545], 38, fill=col)
        M.draw_text_center(d, label, x, 507, 42, M.C_WHITE)
    M.draw_text_center(d, "Үнэгүй видео, дасгал, тоглоом", 600, 590, 32, M.C_INK)
    out = os.path.join(ROOT, "site", "img", "share.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fr.save(out, optimize=True)
    print("Зураг:", out, fr.size)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
