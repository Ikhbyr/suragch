#!/usr/bin/env python
"""Бататгал хичээлийн хэмнэлтэй давтлага (chant): туршилт.

Хэрэглээ:
    python chant/make_chant.py          # chant/chant_msrh.mp4
    python chant/make_chant.py --snap   # зөвхөн шалгах зураг (chant/chant_snap.png)

Бөмбөрийн хэмнэлийг өөрсдөө нийлэгжүүлдэг (зохиогчийн эрхгүй). Хоолой нэг хэмжээнд
хэлж ("би хэлнэ"), дараагийн хэмжээнд хүүхэд давтана ("одоо чи"). Үе, үг бүр цохилт дээр буна.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import make_lesson as M  # noqa: E402

W, H, FPS, SR = M.W, M.H, M.FPS, M.SR
HERE = os.path.join(ROOT, "chant")
BPM = 92
BEAT = 60.0 / BPM
BAR = 4 * BEAT
LEAD = 0.4            # эхний хэмжээ эхлэхээс өмнөх чимээгүй
PRE = 0.04            # load_audio дууны өмнө 0.04 сек үлдээдэг: цохилт дээр яг буулгах засвар
BEAT_VOL = 0.22       # бөмбөрийн чанга (хоолойн оргилтой харьцуулахад)
C_ORANGE = (255, 112, 40)
C_GREEN = (63, 166, 90)
C_BLUE = (43, 103, 216)


# ------------------------------------------------ агуулга
def it(beat, display, say=None, span=1, emoji=None, rng=None):
    return {"beat": beat, "display": display, "say": say, "span": span, "emoji": emoji, "rng": rng}


def bar(section, layout, items, voice=True, **kw):
    return {"section": section, "layout": layout, "items": items, "voice": voice, **kw}


def kid(b):
    """Хүүхдийн ээлж: ижил зураг, ижил тодруулга, хоолойгүй."""
    return {**b, "voice": False}


def letter_bars(L, name, vowels="аэи"):
    b = bar(("Үе хэлье", "🧩"), "tiles",
            [it(0, L.upper() + L, name + ".")] + [it(i + 1, L + v, M.cap(L + v) + ".") for i, v in enumerate(vowels)])
    return [b, kid(b)]


def word_bars(word, syl, emoji):
    items, p = [], 0
    for i, s in enumerate(syl):
        items.append(it(i, s, M.cap(s) + ".", rng=(p, p + len(s))))
        p += len(s)
    items.append(it(len(syl), word, M.cap(word) + ".", span=4 - len(syl), rng=(0, len(word))))
    b = bar(("Үг хэлье", "📖"), "word", items, word=word, syl=syl, emoji=emoji)
    return [b, kid(b)]


def pair_bars(w1, e1, w2, e2):
    b = bar(("Үг хэлье", "📖"), "pair", [it(0, w1, M.cap(w1) + ".", span=2, emoji=e1),
                                       it(2, w2, M.cap(w2) + ".", span=2, emoji=e2)])
    return [b, kid(b)]


def game_bars(order):
    names = {"м": "Эм.", "с": "Эс.", "р": "Эр.", "х": "Хэ."}
    items = [it(i, c.upper() + c, names[c]) for i, c in enumerate(order)]
    quiz = bar(("Хурдан хэл!", "⚡"), "tiles", items, voice=False, reveal=True)
    check = bar(("Хурдан хэл!", "⚡"), "tiles", items)
    return [quiz, check]


def build_bars():
    bars = [bar(None, "title", [it(0, "", "Хамтдаа давтъя!", span=3)], letters="мсрх")]
    names = bar(("Үсгээ хэлье", "🔤"), "tiles",
                [it(i, c.upper() + c, n) for i, (c, n) in enumerate(zip("мсрх", ["Эм.", "Эс.", "Эр.", "Хэ."]))])
    bars += [names, kid(names)]
    for L, n in zip("мсрх", ["Эм.", "Эс.", "Эр.", "Хэ."]):
        bars += letter_bars(L, n)
    rev1 = bar(("Үе хэлье", "🧩"), "tiles", [it(i, s, M.cap(s) + ".") for i, s in enumerate(["ам", "эм", "ас", "эс"])])
    rev2 = bar(("Үе хэлье", "🧩"), "tiles", [it(i, s, M.cap(s) + ".") for i, s in enumerate(["ар", "эр", "ах", "эх"])])
    bars += [rev1, kid(rev1), rev2, kid(rev2)]
    bars += pair_bars("сар", "🌙", "хар", "⚫")
    bars += word_bars("хамар", ["ха", "мар"], "👃")
    bars += word_bars("хэрэм", ["хэ", "рэм"], "🐿️")
    bars += game_bars("хмср") + game_bars("рхсм")
    bars += [bar(None, "outro", [it(0, "", "Маш сайн!", span=2), it(2, "", "Баяртай!", span=2)])]
    return bars


# ------------------------------------------------ бөмбөр (нийлэгжүүлсэн)
def beat_track(bars):
    n = int((LEAD + len(bars) * BAR + 2) * SR)
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)
    t_ = M._t

    def add(t0, sig, amp=1.0):
        i = int(t0 * SR)
        j = min(n, i + len(sig))
        if i < n:
            out[i:j] += amp * sig[:j - i]

    t = t_(0.28)
    kick = (np.sin(2 * np.pi * np.cumsum(48 + 95 * np.exp(-t * 28)) / SR) * np.exp(-t * 11)).astype(np.float32)
    t = t_(0.16)
    noise = np.diff(rng.normal(size=len(t) + 1)).astype(np.float32)
    clap = noise * (np.exp(-t * 32) + 0.6 * np.exp(-np.maximum(0, t - 0.012) * 45) * (t > 0.012))
    t = t_(0.045)
    hat = np.diff(np.diff(rng.normal(size=len(t) + 2))).astype(np.float32) * np.exp(-t * 95)

    def bass(f, dur):
        t = t_(dur)
        env = np.minimum(1, t * 50) * np.exp(-t * 3)
        return (env * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t))).astype(np.float32)

    def chord(ms, dur):
        t = t_(dur)
        env = np.exp(-t * 6) * (1 - np.exp(-t * 300))
        return sum(env * np.sin(2 * np.pi * M._midi(m) * t) for m in ms).astype(np.float32)

    roots = [36, 41, 43, 36]                                 # C F G C
    chords = [[60, 64, 67], [60, 65, 69], [59, 62, 67], [60, 64, 67]]
    for b, spec in enumerate(bars):
        t0 = LEAD + b * BAR
        last = b == len(bars) - 1
        add(t0, kick, 0.9)
        if last:                                             # төгсгөл: ганц цохилт
            add(t0, chord([60, 64, 67, 72], 2.0), 0.10)
            continue
        add(t0 + 2 * BEAT, kick, 0.8)
        add(t0 + BEAT, clap, 0.32)
        add(t0 + 3 * BEAT, clap, 0.32)
        for e in range(8):
            add(t0 + e * BEAT / 2, hat, 0.10 if e % 2 else 0.05)
        r = roots[b % 4]
        add(t0, bass(M._midi(r), BEAT * 1.6), 0.38)
        add(t0 + 2 * BEAT, bass(M._midi(r), BEAT * 1.6), 0.30)
        add(t0, chord(chords[b % 4], BEAT * 2), 0.07)
    out /= float(np.max(np.abs(out))) or 1.0
    return out


# ------------------------------------------------ chant
class Chant:
    def __init__(self, tts):
        self.tts = tts
        self.bars = build_bars()
        self.t = LEAD + len(self.bars) * BAR + 0.8
        self.sounds = []
        for b, spec in enumerate(self.bars):
            t0 = LEAD + b * BAR
            if spec["layout"] == "title":
                for i in range(4):
                    self.sounds.append((t0 + (i + 0) * BEAT, M.SFX_POP))
            if spec["layout"] == "outro":
                self.sounds.append((t0 + 0.9 * BEAT, M.SFX_FANFARE))
            if spec.get("reveal"):
                for x in spec["items"]:
                    self.sounds.append((t0 + x["beat"] * BEAT, M.SFX_POP))
            if not spec["voice"]:
                continue
            for x in spec["items"]:
                if not x["say"]:
                    continue
                narr = spec["layout"] in ("title", "outro")
                a = tts.get(x["say"], tts.rn if narr else tts.rr)
                self.sounds.append((t0 + x["beat"] * BEAT - PRE, a))
                if not tts.collect and M.dur(a) > x["span"] * BEAT + 0.15:
                    print(f"  Анхаар: «{x['say']}» {M.dur(a):.2f} сек, зай {x['span'] * BEAT:.2f} сек")

    # ---------- зураг
    def frame(self, bg, t):
        fr = bg.copy()
        d = ImageDraw.Draw(fr)
        b = int((t - LEAD) // BAR)
        if t < LEAD:
            b = 0
        b = min(b, len(self.bars) - 1)
        spec = self.bars[b]
        lt = t - (LEAD + b * BAR)               # хэмжээн доторх цаг
        beat = lt / BEAT
        cur = int(beat) if lt >= 0 else -1
        since = (beat - cur) * BEAT if cur >= 0 else 9   # цохилтоос хойш өнгөрсөн сек
        bounce = 1 + 0.10 * math.exp(-since * 9)
        voice = spec["voice"]
        lay = spec["layout"]

        if spec["section"]:
            title, emo = spec["section"]
            f = M.font(M.F_HEAD, 40)
            tw = f.getlength(title)
            d.rounded_rectangle([30, 26, 30 + tw + 110, 92], 33, fill=M.C_WHITE, outline=(232, 214, 186), width=3)
            M.paste_emoji(fr, emo, 70, 59, 44)
            d.text((104, 59), title, font=f, fill=M.C_INK, anchor="lm")

        def active(x):
            return x["beat"] <= beat < x["beat"] + x["span"]

        hl = C_OK_FILL if not voice else M.C_HL
        if lay == "title":
            s = M.pop(t, 0.05, 0.5)
            M.draw_text_center(d, "Давтъя!", W / 2, 190, int(120 * max(0.05, s)), C_ORANGE, stroke=8,
                               stroke_fill=M.C_WHITE)
            pos = M.grid(4, 440, 190, 36)
            for i, c in enumerate(spec["letters"]):
                sc = M.pop(lt, i * BEAT, 0.4) * (bounce if cur == i else 1)
                M.draw_tile(d, c.upper() + c, pos[i][0], pos[i][1], 190, 170, scale=sc, text_size=96)
        elif lay == "tiles":
            n = len(spec["items"])
            cell = 200 if n <= 4 else 180
            pos = M.grid(n, 380, cell, 34)
            for i, x in enumerate(spec["items"]):
                if spec.get("reveal"):
                    sc = M.pop(lt, x["beat"] * BEAT, 0.35)
                elif voice and not spec.get("check_all"):
                    sc = max(M.pop(lt, x["beat"] * BEAT - 0.12, 0.35), 0.0)
                else:
                    sc = 1.0
                on = active(x)
                M.draw_tile(d, x["display"], pos[i][0], pos[i][1], cell, cell * 0.85,
                            scale=sc * (bounce if on else 1), fill=hl if on else M.C_WHITE, text_size=cell * 0.46)
        elif lay == "word":
            word, syl = spec["word"], spec["syl"]
            ranges, p = [], 0
            for s_ in syl:
                ranges.append((p, p + len(s_)))
                p += len(s_)
            h, arcs, col = [], [], hl
            for x in spec["items"]:
                if active(x):
                    h = [x["rng"]]
                if beat >= x["beat"]:
                    arcs = ranges[:min(len(syl), spec["items"].index(x) + 1)]
            full = beat >= len(syl)
            if full:
                arcs = ranges
                col = C_GREEN_LIGHT if voice else C_OK_FILL
            sc = bounce if 0 <= cur else 1
            M.paste_emoji(fr, spec["emoji"], W / 2, 170, 140 * (M.pop(lt, len(syl) * BEAT, 0.4) if voice else 1))
            M.draw_word(d, word, W / 2, 385, 180 * sc, hl=h, hl_color=col, arcs=arcs)
        elif lay == "pair":
            for k, x in enumerate(spec["items"]):
                cx = W / 2 + (-260 if k == 0 else 260)
                on = active(x)
                sc = (bounce if on else 1) * (M.pop(lt, x["beat"] * BEAT - 0.12, 0.35) if voice else 1)
                M.paste_emoji(fr, x["emoji"], cx, 230, 140 * sc)
                M.draw_word(d, x["display"], cx, 430, 150 * sc, hl=[(0, len(x["display"]))] if on else (),
                            hl_color=hl)
        elif lay == "outro":
            M.draw_text_center(d, "Маш сайн!", W / 2, 250, int(120 * M.pop(lt, 0.05, 0.5)), C_ORANGE,
                               stroke=8, stroke_fill=M.C_WHITE)
            M.paste_emoji(fr, "⭐", W / 2 - 400, 250, 110 * M.pop(lt, 0.3, 0.5))
            M.paste_emoji(fr, "⭐", W / 2 + 400, 250, 110 * M.pop(lt, 0.45, 0.5))
            if beat >= 2:
                M.draw_text_center(d, "Баяртай!", W / 2, 440, int(90 * M.pop(lt, 2 * BEAT, 0.5)), C_BLUE)
                M.paste_emoji(fr, "👋", W / 2 + 280, 440, 100 * M.pop(lt, 2 * BEAT + 0.1, 0.5))

        # цохилтын цэгүүд + "одоо чи"
        if lay not in ("title", "outro") or lt < BAR:
            for i in range(4):
                cx = W / 2 - 90 + i * 60
                on = i == cur
                r = 20 * (1 + 0.25 * math.exp(-since * 8)) if on else 12
                c = (C_GREEN if not voice else C_ORANGE) if on else (210, 212, 222)
                d.ellipse([cx - r, 655 - r, cx + r, 655 + r], fill=c)
        if not voice and lay in ("tiles", "word", "pair"):
            s = M.pop(lt, 0.0, 0.3)
            f = M.font(M.F_HEAD, 44)
            label = "Одоо чи!"
            tw = f.getlength(label)
            x0 = W / 2 - (tw + 90) / 2
            d.rounded_rectangle([x0, 560, x0 + tw + 90, 616], 28, fill=C_GREEN)
            M.paste_emoji(fr, "🗣️", x0 + 38, 588, 40 * s)
            d.text((x0 + 70, 588), label, font=f, fill=M.C_WHITE, anchor="lm")
        wm = M.watermark_img()
        fr.paste(wm, (20, H - wm.height - 18), wm)
        return fr


C_OK_FILL = (176, 232, 170)
C_GREEN_LIGHT = (196, 240, 190)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = M.load_cfg(os.path.join(ROOT, "lessons", "hicheel_09.json"))
    tts = M.TTS(cfg, os.path.join(ROOT, ".tts_cache"))
    Chant(tts)                     # 1-р алхам: дуунуудыг цуглуулна
    tts.generate_all()
    ch = Chant(tts)
    bg = M.make_bg()
    print(f"Үргэлжлэх хугацаа: {ch.t:.1f} сек, {len(ch.bars)} хэмжээ, {BPM} BPM")
    os.makedirs(HERE, exist_ok=True)
    if "--snap" in sys.argv:
        thumbs = []
        for b in range(len(ch.bars)):
            for f in (0.3, 2.3):
                thumbs.append(ch.frame(bg, LEAD + b * BAR + f * BEAT).resize((320, 180)))
        cols = 6
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * 324, rows * 184), (40, 40, 40))
        for i, th in enumerate(thumbs):
            sheet.paste(th, ((i % cols) * 324 + 2, (i // cols) * 184 + 2))
        p = os.path.join(HERE, "chant_snap.png")
        sheet.save(p)
        print("Зураг:", p)
        return

    total = int((ch.t + 0.5) * SR)
    voice = np.zeros(total, np.float32)
    for at, s in ch.sounds:
        i = int(max(0, at) * SR)
        j = min(total, i + len(s))
        voice[i:j] += s[:j - i]
    voice *= 0.9 / (float(np.max(np.abs(voice))) or 1.0)
    drums = beat_track(ch.bars)[:total]
    drums = np.pad(drums, (0, total - len(drums)))
    mix = voice + M.duck(drums, voice, depth=0.45) * BEAT_VOL
    mix *= min(1.0, 0.95 / (float(np.max(np.abs(mix))) or 1.0))
    wav = os.path.join(HERE, "chant.wav")
    import wave
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype(np.int16).tobytes())
    out = os.path.join(HERE, "chant_msrh.mp4")
    n = int(math.ceil(ch.t * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(ch.frame(bg, i / FPS).tobytes())
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    print("Бэлэн:", out)


if __name__ == "__main__":
    main()
