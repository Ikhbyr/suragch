"""1-р ангийн математикийн хичээлийн видео. make_lesson.py нь "type": "math" JSON-д үүнийг ашиглана.

JSON бүтэц (lessons/1/math/hicheel_01.json):
  "chips": ["1","2","3"], "new_chips": [...]   видеоны баруун дээд буланд, thumbnail дээр
  "topic": "1, 2, 3 тоо"                        гарчиг, тайлбарт
  "sections": [{"key", "title", "emoji", "say", "items": [{"type": ...}, ...]}]

Хэсгийн төрлүүд (items[].type):
  number   {n, emoji, obj?, say?}          шинэ тоотой танилцах: цифр + n зүйл тоолно
  count    {n, emoji}                      зүйлсийг нэг нэгээр тоолно
  howmany  {n, emoji}                      "Хэд байна?" асуулт, 3 хүртэл хүлээгээд хариулна
  sequence {from, to, emoji?, rocket?}     тооны шулуун дээр үсэрч тоолно (буцаж тоолж болно)
  missing  {seq: [1,2,null,4]}             алга болсон тоог олох асуулт
  sign     {sym, word, say, emoji?}        >, <, =, +, − тэмдэгтэй танилцах
  compare  {a, b, emoji, obj}              хоёр эгнээг харьцуулна, тэмдэг гаргана
  split    {n, a, b, emoji}                тоог хоёр хэсэгт задлана
  add      {a, b, emoji, obj, say1?, say2?, story?}   нэмэх (story: тоолохгүй, асуулт болгоно)
  sub      {a, b, emoji, obj, say1?, say2?, story?}   хасах
  expr     {a, op, b}                      "2 + 1 = ?" асуулт (op: + − <>)
"""
import math
import random

import make_lesson as M
from make_lesson import (W, H, pop, ease_out, ease_in_out, clamp, dur, cap, draw_tile, draw_word,
                         draw_text_center, paste_emoji, draw_your_turn, SFX_POP, SFX_DING, SFX_TICK,
                         SFX_WHOOSH, C_WHITE, C_INK, C_HL, C_OK, C_GRAY, C_NUM, Timeline)

# Тооны үгийн хэлбэрүүд (0-10)
NOM = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес", "арав"]
ATTR = ["тэг", "нэг", "хоёр", "гурван", "дөрвөн", "таван", "зургаан", "долоон", "найман", "есөн", "арван"]
ABL = ["тэгээс", "нэгээс", "хоёроос", "гурваас", "дөрвөөс", "таваас", "зургаагаас", "долоогоос",
       "наймаас", "есөөс", "арваас"]
COM = ["тэгтэй", "нэгтэй", "хоёртой", "гуравтай", "дөрөвтэй", "тавтай", "зургаатай", "долоотой",
       "наймтай", "естэй", "аравтай"]
ACC = ["тэгийг", "нэгийг", "хоёрыг", "гурвыг", "дөрвийг", "тавыг", "зургааг", "долоог", "наймыг",
       "есийг", "арвыг"]
OPS = {"+": "нэмэх", "−": "хасах", "-": "хасах"}

SECTION_COLORS = {
    "learn": (255, 138, 60), "count": (67, 170, 80), "seq": (33, 140, 230), "compare": (150, 60, 180),
    "split": (0, 150, 160), "add": (67, 170, 80), "sub": (33, 140, 230), "quiz": (235, 70, 70),
    "story": (230, 110, 160),
}
C_RING = (255, 214, 80)
C_GHOST = (205, 210, 222)


def expr_sentence(a, op, b, c=None):
    """"Хоёр нэмэх нэг тэнцүү гурав." / "Гурав таваас бага." """
    if op in "<>=":
        rel = "бага" if a < b else "их" if a > b else "тэнцүү"
        return f"{cap(NOM[a])} {COM[b] if a == b else ABL[b]} {rel}."
    return f"{cap(NOM[a])} {OPS[op]} {NOM[b]} тэнцүү {NOM[c]}."


def cmp_sign(a, b):
    return "<" if a < b else ">" if a > b else "="


def obj_grid(n, cx, cy, size, per_row=5, gap=0.25):
    """n зүйлийг 5-аар эгнээлж байрлуулна (арвын хүрээ шиг)."""
    step = size * (1 + gap)
    rows = [min(per_row, n - i) for i in range(0, n, per_row)]
    pos = []
    y0 = cy - (len(rows) - 1) * step / 2
    for r, k in enumerate(rows):
        x0 = cx - (k - 1) * step / 2
        pos += [(x0 + j * step, y0 + r * step) for j in range(k)]
    return pos


def ring(d, x, y, r, color=C_RING, width=7):
    d.ellipse([x - r, y - r, x + r, y + r], outline=color, width=width)


def label(d, text, x, y, size=34, fill=C_NUM):
    r = size * 0.75
    d.ellipse([x - r, y - r, x + r, y + r], fill=C_WHITE, outline=(240, 220, 190), width=3)
    draw_word(d, text, x, y, size, color=fill)


class MathLesson(M.Lesson):
    def __init__(self, cfg, tts):
        self.cfg, self.tts = cfg, tts
        self.rn, self.rr = tts.rn, tts.rr
        self.tl = Timeline()
        self.chapters = [(0.0, "Эхлэл")]
        self.chips, self.new_chips = M.overlay_tokens(cfg)

    def num(self, n):
        return self.read(cap(NOM[n]) + ".")

    # -- нийтлэг -------------------------------------------------------
    def intro(self):
        tl, cfg = self.tl, self.cfg
        narr = self.say(cfg["intro"])
        chips = self.chips
        t_l, step = 1.3, 0.3
        tl.sound(0.1, SFX_WHOOSH)
        tl.sound(0.7, narr)
        for i in range(len(chips)):
            tl.sound(t_l + i * step, SFX_POP)
        length = max(0.7 + dur(narr), t_l + len(chips) * step) + 1.2
        cell = min(112, (W - 200) / len(chips) - 18)
        pos = M.grid(len(chips), 520, cell, 18, maxrow=12)
        title, num = cfg.get("title", "Тоолж сурцгаая!"), cfg.get("lesson_number")

        def draw(fr, d, t):
            s = pop(t, 0.1, 0.6)
            draw_text_center(d, title, W / 2, 190, 90 * s, (255, 112, 40), stroke=9 * s, stroke_fill=C_WHITE)
            paste_emoji(fr, "🔢", W / 2 - 520, 190, 105 * pop(t, 0.4))
            paste_emoji(fr, "✏️", W / 2 + 520, 190, 105 * pop(t, 0.5))
            if num:
                draw_text_center(d, f"{num}-р хичээл: {cfg['topic']}", W / 2, 320, 46 * pop(t, 0.6), C_INK)
            for i, ch in enumerate(chips):
                x, y = pos[i]
                draw_tile(d, ch, x, y, cell, cell, scale=pop(t, t_l + i * step), text_size=cell * 0.62,
                          fill=(255, 244, 196) if ch in self.new_chips else C_WHITE)
        tl.add(length, draw, overlay=False)

    def section(self, sec):
        tl = self.tl
        color = SECTION_COLORS.get(sec.get("key"), (100, 100, 100))
        self.chapters.append((tl.t, sec["title"]))
        tl.section = (sec["title"], color)
        narr = self.say(sec["say"])
        tl.sound(0.0, SFX_WHOOSH)
        tl.sound(0.6, narr)
        length = 0.6 + dur(narr) + 0.7

        def draw(fr, d, t):
            bw = W * 0.86 * ease_out(t / 0.5)
            if bw > 20:
                d.rounded_rectangle([W / 2 - bw / 2 + 6, 300, W / 2 + bw / 2 + 6, 490], 60, fill=M.C_SHADOW)
                d.rounded_rectangle([W / 2 - bw / 2, 290, W / 2 + bw / 2, 480], 60, fill=color)
            draw_text_center(d, sec["title"], W / 2, 385, 92 * pop(t, 0.25, 0.5), C_WHITE)
            paste_emoji(fr, sec.get("emoji", ""), W / 2, 175, 140 * pop(t, 0.45))
        tl.add(length, draw, overlay=False)

    def countdown(self, d, t, t0, count=3, cx=W - 120, cy=600):
        if t < t0 or t >= t0 + count:
            return
        k = t - t0
        num, frac = count - int(k), k - int(k)
        r = 50
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_WHITE, outline=(230, 230, 235), width=8)
        d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=(235, 70, 70), width=8)
        draw_text_center(d, str(num), cx, cy, 54 * (1 + 0.25 * max(0, 1 - frac * 4)), (235, 70, 70))

    def progress(self, d, idx, n, done):
        for j in range(n):
            x = W / 2 + (j - (n - 1) / 2) * 34
            fill = (235, 70, 70) if j < idx or (j == idx and done) else (225, 225, 232)
            d.ellipse([x - 10, 690 - 10, x + 10, 690 + 10], fill=fill)

    def expr_tiles(self, d, toks, cy, t, starts, size=118, hidden=None, ok=False):
        """"2 + 1 = 3" мөрийг хавтангаар зурна. hidden: "?" болгох индекс."""
        widths = [size * (1.15 if len(tk) > 1 else 0.95) if tk not in "+−-=<>?" else size * 0.7 for tk in toks]
        gap = 14
        x = W / 2 - (sum(widths) + gap * (len(toks) - 1)) / 2
        for i, (tk, w) in enumerate(zip(toks, widths)):
            cx = x + w / 2
            x += w + gap
            s = pop(t, starts[i]) if starts else 1
            if tk in "+−-=<>":
                draw_text_center(d, tk, cx, cy, size * 0.75 * s, C_INK)
                continue
            show = "?" if i == hidden and not ok else tk
            fill = C_OK if (i == hidden and ok) else (255, 246, 205) if i == hidden else C_WHITE
            draw_tile(d, show, cx, cy, w, size * 1.08, scale=s, text_size=size * 0.66, fill=fill,
                      color=(235, 70, 70) if show == "?" else None)

    # -- хэсгүүд --------------------------------------------------------
    def number(self, it):
        tl, n, e = self.tl, it["n"], it.get("emoji", "⭐")
        t = 0.55
        tl.sound(0.05, SFX_POP)
        a = self.num(n)
        tl.sound(t, a)
        t += dur(a) + 0.45
        counts = []
        for i in range(n):
            c = self.num(i + 1)
            tl.sound(t, SFX_POP)
            tl.sound(t + 0.1, c)
            counts.append(t)
            t += 0.1 + dur(c) + 0.25
        say = it.get("say") or (f"{cap(ATTR[n])} {it['obj']}." if it.get("obj") else "")
        if say:
            t += 0.3
            s = self.say(say)
            tl.sound(t, s)
            t += dur(s)
        length = t + 1.7
        t_turn = t + 0.1
        size = 118 if n <= 5 else 96
        pos = obj_grid(n, 860, 330, size)

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            if 0.55 <= tt <= 0.55 + dur(a):
                s *= 1 + 0.04 * math.sin(2 * math.pi * 2.2 * (tt - 0.55))
            draw_tile(d, "", 330, 370, 360, 430, scale=s)
            draw_word(d, str(n), 330, 330, 250 * s)
            draw_word(d, NOM[n], 330, 515, 64 * s, color=C_INK)
            if n == 0:
                paste_emoji(fr, e, 860, 360, 230 * pop(tt, 0.9))
            for i, (x, y) in enumerate(pos):
                sc = pop(tt, counts[i])
                paste_emoji(fr, e, x, y, size * sc)
                if sc > 0.5:
                    label(d, str(i + 1), x, y + size * 0.62, 26)
            draw_your_turn(fr, tt, t_turn, length)
        tl.add(length, draw)

    def count(self, it):
        tl, n, e = self.tl, it["n"], it.get("emoji", "⭐")
        size = 118 if n <= 5 else 100
        pos = obj_grid(n, W / 2, 310, size, gap=0.5)
        rng = random.Random(n * 31 + len(e))
        pos = [(x + rng.uniform(-12, 12), y + rng.uniform(-10, 10)) for x, y in pos]
        tl.sound(0.05, SFX_POP)
        t = 0.8
        steps = []
        for i in range(n):
            c = self.num(i + 1)
            tl.sound(t, SFX_TICK)
            tl.sound(t + 0.05, c)
            steps.append(t)
            t += 0.05 + dur(c) + 0.3
        t += 0.2
        fin = self.say(f"Бүгд {NOM[n]}.")
        t_fin = t
        tl.sound(t_fin, SFX_DING)
        tl.sound(t_fin + 0.1, fin)
        t = t_fin + 0.1 + dur(fin)
        length = t + 1.6

        def draw(fr, d, tt):
            for i, (x, y) in enumerate(pos):
                on = i < len(steps) and tt >= steps[i]
                if on:
                    d.ellipse([x - size * 0.62, y - size * 0.62, x + size * 0.62, y + size * 0.62],
                              fill=(255, 245, 205))
                paste_emoji(fr, e, x, y, size * pop(tt, 0.05 + i * 0.05) * (1.12 if on and tt - steps[i] < 0.3 else 1))
                if on:
                    label(d, str(i + 1), x, y - size * 0.72, 28)
            if tt >= t_fin:
                s = pop(tt, t_fin)
                draw_tile(d, str(n), W / 2, 600, 150, 140, scale=s, text_size=100, fill=C_OK)
            draw_your_turn(fr, tt, t_fin + 0.2, length)
        tl.add(length, draw)

    def howmany(self, it, idx, total):
        tl, n, e = self.tl, it["n"], it.get("emoji", "⭐")
        size = 112 if n <= 5 else 96
        pos = obj_grid(n, W / 2, 290, size)
        q = self.say("Хэд байна?")
        tl.sound(0.05, SFX_POP)
        tl.sound(0.4, q)
        t0 = 0.4 + dur(q) + 0.3
        for k in range(3):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + 3
        a = self.num(n)
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, a)
        length = t_rev + 0.15 + dur(a) + 1.3

        def draw(fr, d, tt):
            for i, (x, y) in enumerate(pos):
                paste_emoji(fr, e, x, y, size * pop(tt, 0.05 + i * 0.04))
            ok = tt >= t_rev
            draw_tile(d, str(n) if ok else "?", W / 2, 575, 150, 140, scale=pop(tt, 0.3), text_size=100,
                      fill=C_OK if ok else C_WHITE, color=None if ok else (235, 70, 70))
            if ok:
                paste_emoji(fr, "⭐", W / 2 + 85, 515, 80 * pop(tt, t_rev))
            self.countdown(d, tt, t0)
            self.progress(d, idx, total, ok)
        tl.add(length, draw)

    def sequence(self, it):
        tl = self.tl
        a, b = it["from"], it["to"]
        nums = list(range(a, b + 1)) if a <= b else list(range(a, b - 1, -1))
        e = it.get("emoji", "🐸")
        k = len(nums)
        order = sorted(nums)
        cell = min(125, (W - 120) / k - 12)
        xs = [W / 2 + (i - (k - 1) / 2) * (cell + 12) for i in range(k)]
        xpos = {v: xs[order.index(v)] for v in nums}
        tl.sound(0.05, SFX_POP)
        t = 0.9
        steps = []
        for v in nums:
            c = self.num(v)
            tl.sound(t, SFX_POP)
            tl.sound(t + 0.3, c)
            steps.append(t)
            t += 0.3 + dur(c) + 0.25
        t_end = t
        if it.get("rocket"):
            tl.sound(t_end, SFX_WHOOSH)
            t += 1.6
        length = t + 1.4
        cy = 450

        def hop_pos(tt):
            if tt < steps[0]:
                return xpos[nums[0]] - (cell + 12) * (1 if a <= b else -1), cy - cell * 0.95
            i = max(j for j, st in enumerate(steps) if st <= tt)
            p = clamp((tt - steps[i]) / 0.3)
            x1 = xpos[nums[i]]
            x0 = xpos[nums[i - 1]] if i else x1 - (cell + 12) * (1 if a <= b else -1)
            return x0 + (x1 - x0) * ease_in_out(p), cy - cell * 0.95 - math.sin(p * math.pi) * cell * 0.9

        def draw(fr, d, tt):
            d.line([xs[0] - cell * 0.7, cy + cell * 0.62, xs[-1] + cell * 0.7, cy + cell * 0.62],
                   fill=(190, 198, 215), width=6)
            for v in nums:
                i = nums.index(v)
                on = tt >= steps[i]
                cur = on and (i == len(nums) - 1 or tt < steps[i + 1])
                draw_tile(d, str(v), xpos[v], cy, cell, cell * 1.05, scale=pop(tt, 0.05 + order.index(v) * 0.04),
                          text_size=cell * 0.62, fill=C_HL if cur else (255, 246, 205) if on else C_WHITE)
            if it.get("rocket") and tt >= t_end:
                p = (tt - t_end) / 1.6
                paste_emoji(fr, "🚀", W / 2, 260 - 600 * ease_in_out(p) ** 2, 170)
                paste_emoji(fr, "💨", W / 2, 380 - 300 * ease_in_out(p) ** 2, 110 * clamp(p * 3))
            else:
                if it.get("rocket"):
                    paste_emoji(fr, "🚀", W / 2, 260, 170 * pop(tt, 0.2))
                x, y = hop_pos(tt)
                paste_emoji(fr, e, x, y, cell * 0.95)
            draw_your_turn(fr, tt, t_end + 0.1, length)
        tl.add(length, draw)

    def missing(self, it, idx, total):
        tl, seq = self.tl, it["seq"]
        hole = seq.index(None)
        prev = [v for v in seq if v is not None]
        ans = seq[hole - 1] + 1 if hole else seq[1] - 1
        toks = [str(v) if v is not None else str(ans) for v in seq]
        q = self.say("Аль тоо алга байна?")
        tl.sound(0.05, SFX_POP)
        tl.sound(0.4, q)
        t0 = 0.4 + dur(q) + 0.3
        for k in range(3):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + 3
        a = self.num(ans)
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, a)
        length = t_rev + 0.15 + dur(a) + 1.3
        cell = min(130, (W - 160) / len(seq) - 16)
        xs = [W / 2 + (i - (len(seq) - 1) / 2) * (cell + 16) for i in range(len(seq))]
        del prev

        def draw(fr, d, tt):
            ok = tt >= t_rev
            for i, tk in enumerate(toks):
                h = i == hole
                draw_tile(d, "?" if h and not ok else tk, xs[i], 360, cell, cell * 1.1,
                          scale=pop(tt, 0.05 + i * 0.05), text_size=cell * 0.62,
                          fill=C_OK if h and ok else (255, 246, 205) if h else C_WHITE,
                          color=(235, 70, 70) if h and not ok else None)
            if ok:
                paste_emoji(fr, "⭐", xs[hole] + cell * 0.45, 360 - cell * 0.6, 70 * pop(tt, t_rev))
            self.countdown(d, tt, t0)
            self.progress(d, idx, total, ok)
        tl.add(length, draw)

    def sign(self, it):
        tl = self.tl
        s = self.say(it["say"])
        tl.sound(0.05, SFX_POP)
        tl.sound(0.6, s)
        length = 0.6 + dur(s) + 1.5
        ex = it.get("example")   # [3, 5]

        def draw(fr, d, tt):
            sc = pop(tt, 0.05, 0.5)
            draw_tile(d, "", 380, 360, 340, 340, scale=sc)
            draw_text_center(d, it["sym"], 380, 345, 230 * sc, (235, 70, 70) if it["sym"] in "<>" else C_INK)
            draw_text_center(d, it["word"], 880, 250, 96 * pop(tt, 0.4), C_INK)
            if it.get("emoji"):
                paste_emoji(fr, it["emoji"], 880, 420, 150 * pop(tt, 0.7))
            if ex:
                self.expr_tiles(d, [str(ex[0]), it["sym"], str(ex[1])], 590, tt, [1.0, 1.2, 1.4], size=90)
        tl.add(length, draw)

    def compare(self, it):
        tl, a, b = self.tl, it["a"], it["b"]
        e, eb, obj = it.get("emoji", "🍎"), it.get("emoji_b", it.get("emoji", "🍎")), it.get("obj", "")
        m = max(a, b)
        step = min(108, (W - 360) / max(1, m))
        size = step * 0.82
        x0 = 330
        ys = (215, 395)
        tl.sound(0.05, SFX_POP)
        s1 = self.say(it.get("say1") or f"Дээр {ATTR[a]} {obj} байна.")
        s2 = self.say(it.get("say2") or f"Доор {ATTR[b]} {obj} байна.")
        t1 = 0.5
        tl.sound(t1, s1)
        t2 = t1 + dur(s1) + 0.4
        tl.sound(t2, s2)
        t_match = t2 + dur(s2) + 0.3
        tl.sound(t_match, SFX_WHOOSH)
        t_sign = t_match + 1.3
        res = self.say(expr_sentence(a, "<", b))
        tl.sound(t_sign, SFX_DING)
        tl.sound(t_sign + 0.15, res)
        length = t_sign + 0.15 + dur(res) + 1.7

        def draw(fr, d, tt):
            for r, (k, em, ts) in enumerate(((a, e, t1), (b, eb, t2))):
                y = ys[r]
                draw_tile(d, str(k), 150, y, 120, 120, scale=pop(tt, ts), text_size=80)
                for i in range(k):
                    x = x0 + i * step
                    extra = i >= min(a, b) and tt >= t_match + 0.8
                    if extra:
                        d.ellipse([x - size * 0.6, y - size * 0.6, x + size * 0.6, y + size * 0.6], fill=(255, 236, 160))
                    paste_emoji(fr, em, x, y, size * pop(tt, ts + i * 0.06))
            if tt >= t_match:
                p = clamp((tt - t_match) / 0.8)
                for i in range(min(a, b)):
                    x = x0 + i * step
                    yb = ys[0] + size * 0.55 + (ys[1] - ys[0] - size * 1.1) * ease_out(p)
                    d.line([x, ys[0] + size * 0.55, x, yb], fill=(120, 130, 160), width=5)
            if tt >= t_sign - 0.2:
                st = t_sign - 0.2
                self.expr_tiles(d, [str(a), cmp_sign(a, b), str(b)], 590, tt, [st, st + 0.25, st + 0.1], size=100)
            draw_your_turn(fr, tt, t_sign + 0.2 + dur(res), length)
        tl.add(length, draw)

    def split(self, it, idx=None, total=None):
        tl, n, a, b = self.tl, it["n"], it["a"], it["b"]
        quiz = idx is not None
        e = it.get("emoji", "🔵")
        size = min(92, (W - 360) / n * 0.7)
        step = size * 1.42
        tl.sound(0.05, SFX_POP)
        na = self.num(n)
        tl.sound(0.4, na)
        t_split = 0.4 + dur(na) + 0.5
        tl.sound(t_split, SFX_WHOOSH)
        sen = self.say(it.get("say") or f"{cap(NOM[n])} бол {NOM[a]} ба {NOM[b]}.")
        t_say = t_split + 1.0
        t0 = t_rev = None
        if quiz:   # баруун талын тоог нууж, 3 хүртэл хүлээнэ
            t0 = t_split + 1.2
            for k in range(3):
                tl.sound(t0 + k, SFX_TICK)
            t_rev = t0 + 3
            tl.sound(t_rev, SFX_DING)
            t_say = t_rev + 0.15
        tl.sound(t_say, sen)
        length = t_say + dur(sen) + 1.8
        top, bl, br = (W / 2, 140), (W / 2 - 290, 590), (W / 2 + 290, 590)

        def draw(fr, d, tt):
            p = ease_in_out((tt - t_split) / 0.8) if tt > t_split else 0
            if tt > t_split + 0.3:
                q = ease_out((tt - t_split - 0.3) / 0.6)
                for (x1, y1) in (bl, br):
                    d.line([top[0], top[1] + 60, top[0] + (x1 - top[0]) * q, top[1] + 60 + (y1 - 60 - top[1] - 60) * q],
                           fill=(150, 160, 185), width=6)
            draw_tile(d, str(n), *top, 130, 120, scale=pop(tt, 0.05), text_size=84)
            x_start = W / 2 - (n - 1) * step / 2
            for i in range(n):
                x = x_start + i * step + (-110 if i < a else 110) * p
                paste_emoji(fr, e, x, 350, size * pop(tt, 0.1 + i * 0.05))
            if tt > t_split + 0.7:
                s = pop(tt, t_split + 0.7)
                draw_tile(d, str(a), *bl, 130, 120, scale=s, text_size=84, fill=(255, 246, 205))
                hide = quiz and tt < t_rev
                draw_tile(d, "?" if hide else str(b), *br, 130, 120, scale=s, text_size=84,
                          fill=C_OK if quiz and not hide else (255, 246, 205),
                          color=(235, 70, 70) if hide else None)
                draw_text_center(d, "ба", W / 2, 590, 50 * s, C_INK)
            if quiz:
                self.countdown(d, tt, t0)
                self.progress(d, idx, total, tt >= t_rev)
            draw_your_turn(fr, tt, t_say + dur(sen) + 0.1, length)
        tl.add(length, draw)

    def _arith(self, it, op, idx=None, total=None):
        """Нэмэх, хасах: зүйлсээр харуулж, тоолоод, илэрхийлэл бичнэ. story=True бол асуулт болгоно."""
        tl, a, b = self.tl, it["a"], it["b"]
        c = a + b if op == "+" else a - b
        e, obj = it.get("emoji", "🍎"), it.get("obj", "")
        story = it.get("story")
        add = op == "+"
        size = 92 if max(a, b, c) <= 5 else 78
        if add:
            pa = obj_grid(a, W / 2 - 250, 290, size, gap=0.45)
            pb = obj_grid(b, W / 2 + 250, 290, size, gap=0.45)
        else:
            pa = obj_grid(a, W / 2, 290, size, gap=0.45)
            pb = []
        tl.sound(0.05, SFX_POP)
        s1 = self.say(it.get("say1") or f"{cap(ATTR[a])} {obj} байна.")
        t1 = 0.5
        tl.sound(t1, s1)
        t2 = t1 + dur(s1) + 0.4
        s2 = self.say(it.get("say2") or (f"Дахиад {ATTR[b]} {obj} нэмэгдлээ." if add else f"Үүнээс {ACC[b]} нь авъя."))
        tl.sound(t2, SFX_WHOOSH)
        tl.sound(t2 + 0.3, s2)
        t = t2 + 0.3 + dur(s2) + 0.4
        counted = list(pa) + list(pb) if add else pa[:c]
        steps = []
        if story and it.get("question"):
            q = self.say(it["question"])
            tl.sound(t, q)
            t += dur(q) + 0.3
        if not story:
            q = self.say("Бүгд хэд болов? Тоолъё." if add else
                         "Хэд үлдэв? Тоолъё." if c else "Хэд үлдэв? Юу ч үлдсэнгүй.")
            tl.sound(t, q)
            t += dur(q) + 0.3
            for i in range(len(counted)):
                cl = self.num(i + 1)
                tl.sound(t, SFX_TICK)
                tl.sound(t + 0.05, cl)
                steps.append(t)
                t += 0.05 + dur(cl) + 0.22
            t += 0.3
        toks = [str(a), "+" if add else "−", str(b), "=", str(c)]
        t_expr = t
        starts = [t_expr + i * 0.25 for i in range(5)]
        for st in starts:
            tl.sound(st, SFX_POP)
        t_rev = None
        if story:
            t0 = t_expr + 1.4
            for k in range(3):
                tl.sound(t0 + k, SFX_TICK)
            t_rev = t0 + 3
            tl.sound(t_rev, SFX_DING)
            t_say = t_rev + 0.15
        else:
            t_say = t_expr + 1.4
        sen = self.say(expr_sentence(a, op, b, c))
        tl.sound(t_say, sen)
        t = t_say + dur(sen)
        length = t + 1.7

        def draw(fr, d, tt):
            # эхний бүлэг
            for i, (x, y) in enumerate(pa):
                gone = (not add) and i >= c
                if gone and tt >= t2:
                    p = ease_in_out((tt - t2) / 0.9)
                    r = size * 0.5
                    d.ellipse([x - r, y - r, x + r, y + r], outline=C_GHOST, width=5)
                    if p < 1:
                        paste_emoji(fr, e, x + 700 * p ** 2, y - 260 * p, size * (1 - 0.3 * p))
                    continue
                on = i < len(steps) and tt >= steps[i]
                if on:
                    d.ellipse([x - size * 0.6, y - size * 0.6, x + size * 0.6, y + size * 0.6], fill=(255, 245, 205))
                paste_emoji(fr, e, x, y, size * pop(tt, t1 - 0.3 + i * 0.05))
                if on:
                    label(d, str(i + 1), x, y - size * 0.7, 26)
            # нэмэгдэх бүлэг
            if add and tt >= t2:
                draw_text_center(d, "+", W / 2, 280, 110 * pop(tt, t2), C_INK)
                for j, (x, y) in enumerate(pb):
                    p = ease_out((tt - t2 - j * 0.08) / 0.7)
                    k = len(pa) + j
                    on = k < len(steps) and tt >= steps[k]
                    xx = x + (W - x + 100) * (1 - p)
                    if on:
                        d.ellipse([xx - size * 0.6, y - size * 0.6, xx + size * 0.6, y + size * 0.6], fill=(255, 245, 205))
                    paste_emoji(fr, e, xx, y, size)
                    if on:
                        label(d, str(k + 1), xx, y - size * 0.7, 26)
            if tt >= t_expr:
                self.expr_tiles(d, toks, 590, tt, starts, size=104,
                                hidden=4 if story else None, ok=(not story) or tt >= t_rev)
            if story:
                self.countdown(d, tt, t_expr + 1.4)
                if idx is not None:
                    self.progress(d, idx, total, t_rev is not None and tt >= t_rev)
            draw_your_turn(fr, tt, t_say + dur(sen) + 0.1, length)
        tl.add(length, draw)

    def expr(self, it, idx, total):
        tl, a, op, b = self.tl, it["a"], it["op"], it["b"]
        if op in "<>=":
            toks, hidden = [str(a), cmp_sign(a, b), str(b)], 1
            sen = expr_sentence(a, "<", b)
        else:
            c = a + b if op == "+" else a - b
            toks, hidden = [str(a), op, str(b), "=", str(c)], 4
            sen = expr_sentence(a, op, b, c)
        tl.sound(0.05, SFX_POP)
        t0 = 0.8
        for k in range(3):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + 3
        s = self.say(sen)
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, s)
        length = t_rev + 0.15 + dur(s) + 1.4
        e = it.get("emoji")

        def draw(fr, d, tt):
            ok = tt >= t_rev
            if hidden == 1:   # харьцуулах: тэмдгийн оронд асуултын хавтан
                xs = [W / 2 - 260, W / 2, W / 2 + 260]
                for i, tk in enumerate(toks):
                    h = i == 1
                    draw_tile(d, "?" if h and not ok else tk, xs[i], 360, 190, 200, scale=pop(tt, 0.05 + i * 0.08),
                              text_size=130, fill=C_OK if h and ok else (255, 246, 205) if h else C_WHITE,
                              color=(235, 70, 70) if h and not ok else C_INK if h else None)
            else:
                self.expr_tiles(d, toks, 360, tt, [0.05 + i * 0.08 for i in range(len(toks))], size=150,
                                hidden=hidden, ok=ok)
            if e:
                paste_emoji(fr, e, W / 2, 150, 110 * pop(tt, 0.2))
            if ok:
                paste_emoji(fr, "⭐", W / 2 + 330, 230, 90 * pop(tt, t_rev))
            self.countdown(d, tt, t0)
            self.progress(d, idx, total, ok)
        tl.add(length, draw)

    # -- угсралт -------------------------------------------------------
    def build(self):
        self.intro()
        for sec in self.cfg["sections"]:
            self.section(sec)
            items = sec["items"]
            quizzes = [it for it in items if it["type"] in ("howmany", "missing", "expr")
                       or (it["type"] in ("add", "sub") and it.get("story"))
                       or (it["type"] == "split" and it.get("quiz"))]
            qi = 0
            for it in items:
                ty = it["type"]
                if it in quizzes:
                    args = (qi, len(quizzes))
                    qi += 1
                else:
                    args = ()
                if ty == "add":
                    self._arith(it, "+", *args)
                elif ty == "sub":
                    self._arith(it, "−", *args)
                else:
                    getattr(self, ty)(it, *args)
        self.outro()
        return self.tl
