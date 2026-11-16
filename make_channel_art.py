#!/usr/bin/env python
"""YouTube сувгийн баннер (2560x1440) болон профайл зураг (800x800) үүсгэнэ.

Хэрэглээ:  python make_channel_art.py  ->  youtube/channel_banner.png, youtube/channel_profile.png
Баннерын бүх төхөөрөмж дээр харагдах хэсэг: голын 1546x423 (энд бүх бичиг байрлана).
"""
import os

from PIL import Image, ImageDraw

import make_lesson as M

ROOT = os.path.dirname(os.path.abspath(__file__))
COVER = (43, 103, 216)
PAPER = (253, 254, 255)
RULE = (207, 224, 244)
MARGIN = (243, 160, 160)
INK_SOFT = (86, 96, 138)
TILE_BORDER = (231, 220, 198)


def cover_bg(w, h, step):
    im = Image.new("RGB", (w, h), COVER)
    d = ImageDraw.Draw(im)
    r = max(2, step // 12)
    for y in range(step // 2, h, step):
        for x in range(step // 2, w, step):
            d.ellipse([x - r, y - r, x + r, y + r], fill=(66, 122, 224))
    return im


def paper(d, box, line, margin_x, radius):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0 + 10, y0 + 22, x1 + 10, y1 + 26], radius, fill=(28, 70, 160))
    d.rounded_rectangle(box, radius, fill=PAPER)
    y = y0 + line
    while y < y1 - radius * 0.6:
        d.line([x0 + 4, y, x1 - 4, y], fill=RULE, width=3)
        y += line
    d.line([margin_x, y0, margin_x, y1], fill=MARGIN, width=4)


def spiral(d, x0, x1, y, gap, r):
    x = x0 + gap / 2
    while x < x1:
        d.ellipse([x - r, y - r, x + r, y + r], fill=COVER)
        d.rounded_rectangle([x - r * 0.55, y - r * 3.2, x + r * 0.55, y + r * 0.2], int(r * 0.5), fill=(200, 208, 222))
        x += gap


def colored_text(d, text, cx, cy, size, path=M.F_HEAD, stroke=0):
    f = M.font(path, size)
    l, t, r, b = f.getbbox(text, anchor="ls")
    x = cx - (l + r) / 2
    base = cy - (t + b) / 2
    for i, ch in enumerate(text):
        d.text((x + f.getlength(text[:i]), base), ch, font=f, fill=M.letter_color(ch), anchor="ls",
               stroke_width=stroke, stroke_fill=PAPER)


def tile(ch, size, angle, new=False):
    pad = int(size * 0.25)
    im = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = int(size * 0.2)
    d.rounded_rectangle([pad + 8, pad + 14, pad + size + 8, pad + size + 14], r, fill=(25, 66, 150, 255))
    d.rounded_rectangle([pad, pad, pad + size, pad + size], r, fill=(255, 241, 184) if new else (255, 255, 255),
                        outline=TILE_BORDER, width=max(4, size // 22))
    M.draw_word(d, ch, pad + size / 2, pad + size / 2, size * 0.66)
    return im.rotate(angle, resample=Image.BICUBIC, expand=False)


def banner(path):
    W, H = 2560, 1440
    im = cover_bg(W, H, 46)
    d = ImageDraw.Draw(im)
    # дэвтрийн хуудас (бичиг нь голын аюулгүй хэсэгт)
    box = (430, 470, 2130, 975)
    paper(d, box, 62, 560, 26)
    spiral(d, box[0] + 30, box[2] - 30, box[1] + 4, 62, 13)
    colored_text(d, "Уншиж сурцгаая!", 1300, 655, 148)
    M.draw_text_center(d, "1-р ангийн уншлагын хичээл", 1300, 830, 70, INK_SOFT)
    # хажуугийн үсгийн хавтангууд (компьютер, ТВ дээр харагдана)
    left = [("а", 150, 520, -10), ("м", 300, 700, 8), ("б", 130, 860, 6), ("э", 340, 1010, -7)]
    right = [("с", 2430, 520, 9, True), ("ү", 2260, 700, -8), ("и", 2440, 870, -5), ("ө", 2230, 1010, 7)]
    for item in left + right:
        ch, x, y, a = item[:4]
        new = len(item) > 4
        t = tile(ch, 190, a, new)
        im.paste(t, (int(x - t.width / 2), int(y - t.height / 2)), t)
    M.paste_emoji(im, "📚", 1960, 845, 90)
    M.paste_emoji(im, "✏️", 650, 845, 80)
    im.save(path, optimize=True)


def profile(path):
    S = 800
    im = cover_bg(S, S, 40)
    d = ImageDraw.Draw(im)
    box = (170, 170, 630, 630)
    paper(d, box, 54, 230, 60)
    M.draw_word(d, "Аа", S / 2 + 20, S / 2 + 6, 260)
    im.save(path, optimize=True)


def watermark(path):
    """YouTube-ийн "Video watermark": тунгалаг дэвсгэртэй дөрвөлжин PNG (150x150-аас том)."""
    S = 300
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([14, 14, S - 14, S - 14], 56, fill=COVER + (255,))
    box = (34, 34, S - 34, S - 34)
    d.rounded_rectangle(box, 40, fill=PAPER + (255,))
    y = box[1] + 46
    while y < box[3] - 30:
        d.line([box[0] + 6, y, box[2] - 6, y], fill=RULE + (255,), width=4)
        y += 46
    d.line([78, box[1], 78, box[3]], fill=MARGIN + (255,), width=5)
    M.draw_word(d, "Аа", S / 2 + 12, S / 2 + 4, 150)
    im.save(path, optimize=True)


def main():
    out = os.path.join(ROOT, "youtube")
    os.makedirs(out, exist_ok=True)
    banner(os.path.join(out, "channel_banner.png"))
    profile(os.path.join(out, "channel_profile.png"))
    watermark(os.path.join(out, "channel_watermark.png"))
    print("Бэлэн: youtube/channel_banner.png, channel_profile.png, channel_watermark.png")


if __name__ == "__main__":
    main()
