#!/usr/bin/env python
"""Сайтыг сурталчлах босоо (9:16) богино видео: Facebook Reels, YouTube Shorts, TikTok.

Хэрэглээ:
    python promo/make_reel.py          # promo/reel_suragch.mp4
    python promo/make_reel.py --snap   # зөвхөн шалгах зураг

Сайтын дэлгэцийн зургууд promo/shots/*.png (утсан дээрх харагдац, 810x1760).
Хичээлийн хэсгийг бичлэгээс биш, хичээлийн JSON-оос шууд зурж авна.
"""
import math
import os
import subprocess
import sys
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import make_lesson as M  # noqa: E402

RW, RH, FPS, SR = 1080, 1920, M.FPS, M.SR
HERE = os.path.join(ROOT, "promo")
SHOTS = os.path.join(HERE, "shots")
C_BLUE = (43, 103, 216)
C_ORANGE = (255, 112, 40)
C_GREEN = (63, 166, 90)
C_PINK = (221, 68, 121)

VOICE_CFG = {"tts_provider": "chimege",
             "chimege": {"voice": "FEMALE4v2", "pitch": 1.05, "speed_narration": 0.95, "speed_reading": 0.8}}


# ------------------------------------------------ туслах зураг
def reel_bg():
    top, bot = np.array([255, 247, 226], float), np.array([224, 240, 255], float)
    y = np.linspace(0, 1, RH)[:, None, None]
    arr = np.broadcast_to(top * (1 - y) + bot * y, (RH, RW, 3)).astype(np.uint8)
    im = Image.fromarray(arr.copy()).convert("RGBA")
    ov = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    import random
    rng = random.Random(11)
    cols = [(255, 190, 120), (140, 200, 255), (255, 160, 190), (160, 220, 150), (255, 225, 120)]
    for _ in range(22):
        r = rng.randint(40, 140)
        x, y0 = rng.choice([rng.randint(-60, 160), rng.randint(RW - 160, RW + 60)]), rng.randint(-60, RH + 60)
        d.ellipse([x - r, y0 - r, x + r, y0 + r], fill=rng.choice(cols) + (50,))
    return Image.alpha_composite(im, ov).convert("RGB")


def lines_center(d, lines, cx, cy, size, fill, gap=1.18, stroke=0, stroke_fill=None):
    step = size * gap
    y0 = cy - step * (len(lines) - 1) / 2
    for i, ln in enumerate(lines):
        M.draw_text_center(d, ln, cx, y0 + i * step, size, fill, stroke=stroke, stroke_fill=stroke_fill)


def ease(t, a, b):
    return M.ease_out(M.clamp((t - a) / (b - a)))


@lru_cache(None)
def shot(name, w):
    im = Image.open(os.path.join(SHOTS, name + ".png")).convert("RGB")
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


@lru_cache(None)
def round_mask(w, h, r):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], r, fill=255)
    return m


def phone(fr, name, cx, top, w=600, enter=1.0, tap=None, t=0.0):
    """Утасны хүрээтэй сайтын зураг. tap=(x, y, t0): зураг доторх цэг (0..1) дээр хуруугаар дарна."""
    sc = shot(name, w)
    pad = 18
    fw, fh = w + 2 * pad, sc.height + 2 * pad
    y = top + (1 - enter) * 500
    x0 = int(cx - fw / 2)
    d = ImageDraw.Draw(fr)
    d.rounded_rectangle([x0 + 10, y + 16, x0 + fw + 10, y + fh + 16], 64, fill=(196, 206, 226))
    d.rounded_rectangle([x0, y, x0 + fw, y + fh], 64, fill=(34, 38, 54))
    fr.paste(sc, (x0 + pad, int(y + pad)), round_mask(sc.width, sc.height, 48))
    d.rounded_rectangle([cx - 70, y + pad + 10, cx + 70, y + pad + 34], 12, fill=(34, 38, 54))  # камер
    if tap:
        px, py, t0 = x0 + pad + tap[0] * sc.width, y + pad + tap[1] * sc.height, tap[2]
        k = t - t0
        if -0.6 < k < 1.2:
            if k > 0:   # дарсан долгион
                r = 30 + 110 * M.ease_out(min(1, k / 0.6))
                a = int(170 * max(0, 1 - k / 0.8))
                ov = Image.new("RGBA", fr.size, (0, 0, 0, 0))
                ImageDraw.Draw(ov).ellipse([px - r, py - r, px + r, py + r], fill=(255, 210, 60, a))
                fr.paste(Image.alpha_composite(fr.convert("RGBA"), ov).convert("RGB"))
            off = 120 * (1 - M.ease_out(M.clamp((k + 0.6) / 0.6)))
            M.paste_emoji(fr, "👆", px + 30 + off, py + 70 + off, 130)


def chip(fr, d, emoji, text, cx, cy, col, size=44):
    f = M.font(M.F_HEAD, size)
    e = size * 1.25
    w = f.getlength(text) + e + size * 1.6
    d.rounded_rectangle([cx - w / 2, cy - size * 0.95, cx + w / 2, cy + size * 0.95], size, fill=col)
    M.paste_emoji(fr, emoji, cx - w / 2 + size * 0.7 + e / 2, cy, e)
    d.text((cx - w / 2 + size * 0.9 + e, cy), text, font=f, fill=M.C_WHITE, anchor="lm")


# ------------------------------------------------ хичээлийн хэсэг
class Clip:
    """Хичээлийн видеоны хэсгийг (16:9) шууд зурж авна."""

    def __init__(self, path, start):
        cfg = M.load_cfg(path)
        tts = M.TTS(cfg, os.path.join(ROOT, ".tts_cache"))
        cls = M.lesson_class(cfg)
        cls(cfg, tts).build()
        tts.generate_all()
        self.tl = cls(cfg, tts).build()
        self.starts = [s[0] for s in self.tl.scenes]
        self.tokens = M.overlay_tokens(cfg)
        self.bg = M.make_bg()
        self.start = start

    def frame(self, t, w):
        im = M.frame_at(self.tl, self.bg, self.starts, self.start + t, *self.tokens)
        return im.resize((w, round(w * M.H / M.W)), Image.LANCZOS)


# ------------------------------------------------ үзэгдлүүд
class Reel:
    def __init__(self, tts):
        self.tts = tts
        self.scenes, self.sounds, self.t = [], [], 0.0

    def say(self, text):
        return self.tts.get(text, self.tts.rn)

    def add(self, voice, draw, pre=0.35, post=0.6, min_len=0.0, extra=()):
        """voice: яриа; extra: [(цаг, дуу)] нэмэлт дуу."""
        a = self.say(voice) if voice else None
        length = max(min_len, pre + (M.dur(a) if a is not None else 0) + post)
        if a is not None:
            self.sounds.append((self.t + pre, a))
        for at, s in extra:
            self.sounds.append((self.t + at, s))
        self.scenes.append((self.t, length, draw))
        self.t += length

    def build(self):
        mclip = Clip(os.path.join(ROOT, "lessons", "hicheel_09.json"), 78.5)
        nclip = Clip(os.path.join(ROOT, "lessons", "1", "math", "hicheel_08.json"), 26.5)
        logo = M.watermark_img(3)

        # 1. Асуулт (hook)
        tiles = ["а", "х", "м", "1", "+", "2"]

        def hook(fr, d, t):
            s = M.pop(t, 0.0, 0.6)
            lines_center(d, ["Хүүхэд тань", "үсэг, тоо", "сурч байна уу?"], RW / 2, 640, 104 * (0.6 + 0.4 * s),
                         C_ORANGE, stroke=10, stroke_fill=M.C_WHITE)
            cell, gap = 140, 22
            x0 = RW / 2 - (3 * cell + 2 * gap) / 2 + cell / 2
            for i, tk in enumerate(tiles):
                p = M.pop(t, 0.5 + i * 0.16, 0.45)
                if p > 0:
                    M.draw_tile(d, tk, x0 + (i % 3) * (cell + gap), 1080 + (i // 3) * (cell + gap + 10),
                                cell, cell * 1.08, scale=p, text_size=92,
                                fill=(255, 238, 160) if tk == "+" else M.C_WHITE)
        self.add("Хүүхэд тань үсэг, тоо сурч байна уу?", hook, pre=0.3, post=0.9,
                 extra=[(0.5 + i * 0.16, M.SFX_POP) for i in range(len(tiles))] + [(0.0, M.SFX_WHOOSH)])

        # 2. Видео хичээл
        def videos(fr, d, t):
            fr.paste(logo, (int(RW / 2 - logo.width / 2), 250), logo)
            lines_center(d, ["1-р ангийн", "видео хичээл"], RW / 2, 520, 86, M.C_INK)
            clip = mclip if t < 3.4 else nclip
            k = t if t < 3.4 else t - 3.4
            cw = 980
            im = clip.frame(k, cw)
            y = 700 + (1 - ease(t, 0, 0.5)) * 300
            x = (RW - cw) // 2
            d.rounded_rectangle([x - 12, y - 12, x + cw + 12, y + im.height + 12], 40, fill=(34, 38, 54))
            fr.paste(im, (x, int(y)), round_mask(im.width, im.height, 30))
            chip(fr, d, "📖", "Монгол хэл", RW / 2 - 235, 1420, (33, 140, 230))
            chip(fr, d, "🔢", "Математик", RW / 2 + 245, 1420, C_GREEN)
            if t > 0.8:
                M.draw_text_center(d, "Үсэг нэг нэгээр, тоо 1-ээс эхлэн", RW / 2, 1560, 44, M.C_INK, path=M.F_TEXT)
        self.add("Сурагч сайтад нэгдүгээр ангийн Монгол хэл, Математикийн видео хичээлүүд бий.", videos,
                 min_len=6.8, post=0.5)

        # 3. Дарахад дуудлага сонсогдоно
        ah = self.tts.get("Ах.", self.tts.rr)

        def tap(fr, d, t):
            lines_center(d, ["Дарахад", "дуудлага нь сонсогдоно"], RW / 2, 210, 70, C_BLUE)
            M.paste_emoji(fr, "🔊", RW - 110, 120, 90)
            phone(fr, "words", RW / 2, 360, enter=ease(t, 0, 0.5), tap=(0.317, 0.68, 2.4), t=t)
        self.add("Үсэг, үг дээр дарахад дуудлага нь сонсогдоно.", tap, min_len=4.6, post=0.4,
                 extra=[(2.45, M.SFX_POP), (2.6, ah)])

        # 4. Тоглоом, бодлого
        def game(fr, d, t):
            lines_center(d, ["Бодлого, тоглоом", "хичээл бүрт"], RW / 2, 210, 74, C_PINK)
            M.paste_emoji(fr, "🎮", RW - 110, 120, 90)
            name = "prob" if t < 2.6 else "letters"
            phone(fr, name, RW / 2, 360, enter=ease(t, 0, 0.5) if t < 2.6 else 1.0,
                  tap=(0.83, 0.56, 1.5) if name == "prob" else None, t=t)
        self.add("Хичээл бүрийн дараа бодлого, тоглоом бий.", game, min_len=4.8,
                 extra=[(1.55, M.SFX_DING)])

        # 5. Үнэгүй
        badges = ["Үнэгүй", "Бүртгэлгүй", "Зар сурталчилгаагүй", "Утас, компьютер дээр"]

        def free(fr, d, t):
            M.draw_text_center(d, "Бүгд", RW / 2, 470, 96, M.C_INK)
            for i, b in enumerate(badges):
                p = M.pop(t, 0.3 + i * 0.5, 0.45)
                if p <= 0:
                    continue
                y = 680 + i * 190
                w = 820
                d.rounded_rectangle([RW / 2 - w / 2, y - 70, RW / 2 + w / 2, y + 70], 70,
                                    fill=M.C_WHITE, outline=(214, 226, 240), width=5)
                M.paste_emoji(fr, "✅", RW / 2 - w / 2 + 90, y, 84 * p)
                d.text((RW / 2 - w / 2 + 165, y), b, font=M.font(M.F_HEAD, int(58 * (0.7 + 0.3 * p))),
                       fill=M.C_INK, anchor="lm")
        self.add("Бүгд үнэгүй. Бүртгэл шаардлагагүй, зар сурталчилгаагүй.", free, min_len=3.0 + 0.5 * len(badges),
                 extra=[(0.3 + i * 0.5, M.SFX_POP) for i in range(len(badges))])

        # 6. Уриалга
        def cta(fr, d, t):
            fr.paste(logo, (int(RW / 2 - logo.width / 2), 330), logo)
            M.draw_text_center(d, "Одоо орж үзээрэй!", RW / 2, 620, 86, C_ORANGE, stroke=8, stroke_fill=M.C_WHITE)
            p = M.pop(t, 0.4, 0.6)
            w = 900 * (0.6 + 0.4 * p)
            d.rounded_rectangle([RW / 2 - w / 2, 800, RW / 2 + w / 2, 960], 80, fill=C_BLUE)
            M.draw_text_center(d, "suragch.cloud", RW / 2, 880, int(92 * (0.6 + 0.4 * p)), M.C_WHITE)
            if t > 1.2:
                M.draw_text_center(d, "Линк коммент дээр", RW / 2 + 40, 1060, 50, M.C_INK, path=M.F_TEXT)
                M.paste_emoji(fr, "👇", RW / 2 - 250, 1060, 64)
            phone(fr, "list", RW / 2, 1180, w=520, enter=ease(t, 0.6, 1.2))
        self.add("Одоо орж үзээрэй! Сурагч цэг клауд.", cta, min_len=4.5, post=1.4,
                 extra=[(0.4, M.SFX_DING), (0.0, M.SFX_WHOOSH)])

    # ------------------------------------------------ гаргах
    def frame(self, bg, t):
        k = max(i for i, s in enumerate(self.scenes) if s[0] <= t + 1e-9)
        st, ln, draw = self.scenes[k]
        fr = bg.copy()
        d = ImageDraw.Draw(fr)
        draw(fr, d, t - st)
        wm = M.watermark_img(2)
        fr.paste(wm, (RW - wm.width - 36, RH - wm.height - 60), wm)
        return fr


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tts = M.TTS(VOICE_CFG, os.path.join(ROOT, ".tts_cache"))
    Reel(tts).build()             # 1-р алхам: дуунуудыг цуглуулна
    tts.generate_all()
    reel = Reel(tts)
    reel.build()
    bg = reel_bg()
    print(f"Үргэлжлэх хугацаа: {reel.t:.1f} сек, {len(reel.scenes)} үзэгдэл")
    if "--snap" in sys.argv:
        thumbs = []
        for st, ln, _ in reel.scenes:
            for f in (0.35, 0.85):
                thumbs.append(reel.frame(bg, st + ln * f).resize((270, 480)))
        sheet = Image.new("RGB", (len(thumbs) * 274, 484), (40, 40, 40))
        for i, th in enumerate(thumbs):
            sheet.paste(th, (i * 274 + 2, 2))
        p = os.path.join(HERE, "reel_snap.png")
        sheet.save(p)
        print("Зураг:", p)
        return

    class TL:   # write_wav-д тохирох хэлбэр
        sounds, t = reel.sounds, reel.t
    wav = os.path.join(HERE, "reel.wav")
    out = os.path.join(HERE, "reel_suragch.mp4")
    M.write_wav(TL, wav, music_vol=0.22)
    n = int(math.ceil(reel.t * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{RW}x{RH}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(reel.frame(bg, i / FPS).tobytes())
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("Бэлэн:", out)


if __name__ == "__main__":
    main()
