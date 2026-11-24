#!/usr/bin/env python
"""Нэгдүгээр ангийн уншлагын хичээлийн видео үүсгэгч.

Хэрэглээ:
    python make_lesson.py lessons/hicheel_07.json            # видео гаргана -> videos/
    python make_lesson.py lessons/hicheel_07.json --snap     # зөвхөн шалгах зураг (contact sheet)
    python make_lesson.py lessons/hicheel_07.json --no-watermark   # буланд лого оруулахгүй

Шинэ үсэг нэмэхдээ JSON файлыг хуулж, "letters", "new_letters", "letter_info",
"words", "sentences", "quiz" хэсгийг шинэчилнэ. Уншуулах үг, өгүүлбэр нь зөвхөн
үзсэн үсгүүдээс бүрдэх ёстой - скрипт үүнийг шалгана.
"""
import sys, os, json, asyncio, hashlib, subprocess, math, random, wave, bisect, re, difflib
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import edge_tts

if __name__ == "__main__":   # make_math.py "import make_lesson" хийхэд энэ модулийг дахин ачаалахгүй
    sys.modules.setdefault("make_lesson", sys.modules["__main__"])

W, H, FPS, SR = 1280, 720, 25, 24000
BRAND = "Сурагч"   # суваг, сайтын нэр
FD = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
F_TEXT = os.path.join(FD, "segoeuib.ttf")   # уншуулах текст (хоёр давхар "а")
F_HEAD = os.path.join(FD, "seguibl.ttf")    # гарчиг
F_EMOJI = os.path.join(FD, "seguiemj.ttf")

VOWELS = set("аэиоуөүыяеёю")
SEMIVOWELS = set("й")
DESCENDERS = set("руфдцщ")
C_VOWEL = (222, 44, 44)      # эгшиг - улаан
C_CONS = (28, 92, 205)       # гийгүүлэгч - хөх
C_SEMI = (142, 58, 172)      # й - ягаан
C_NUM = (236, 104, 24)       # тоо - улбар шар
C_INK = (55, 55, 75)
C_HL = (255, 224, 90)
C_OK = (196, 240, 190)
C_WHITE = (255, 255, 255)
C_SHADOW = (206, 214, 228)
C_GRAY = (175, 175, 185)
C_DIM = (196, 198, 210)      # үзээгүй үсэг (сонсох үгэнд)
NEW_LETTER_SECTION = {"title": "Шинэ үсэг", "emoji": "⭐",
                      "say": "Өнөөдрийн шинэ үсэгтэй танилцъя. Би хэлнэ, чи давтаж хэлээрэй."}
SECTION_COLORS = {
    "letters": (255, 138, 60), "syllables": (67, 170, 80), "words": (33, 140, 230),
    "sentences": (150, 60, 180), "quiz": (235, 70, 70), "listen": (230, 110, 160),
    "syltype": (0, 150, 160), "sort": (236, 104, 24), "story": (63, 140, 90), "questions": (150, 60, 180),
    "characters": (230, 110, 160), "magic": (142, 58, 172), "chant": (236, 104, 24),
}
C_OPEN = (67, 170, 80)       # задгай үе
C_CLOSED = (221, 68, 121)    # битүү үе


REBUS = re.compile(r"\{([^:}]+):([^}]+)\}")


def rebus(tk):
    """"{од:⭐}!" -> ("од", "⭐", "!"). Зурган үг биш бол None."""
    m = REBUS.match(tk)
    return (m.group(1), m.group(2), tk[m.end():]) if m else None


def plain(text):
    """Зурган үгийг унших үгээр нь солино: "Ийм их {од:⭐}!" -> "Ийм их од!"."""
    return REBUS.sub(lambda m: m.group(1), text)


CHANT_BPM = 100                  # арын аятай ижил хурд (make_music bpm=100), хэмжээ нь давхцана
CHANT_BEAT = 60.0 / CHANT_BPM
CHANT_BAR = 4 * CHANT_BEAT


def drum_loop(bars, amp=0.24):
    """Хэмнэлийн бөмбөр: зөвхөн цохилт (kick, алга ташилт, шажигнуур), аялгуугүй тул арын аятай зөрчилдөхгүй."""
    n = int((bars * CHANT_BAR + 0.5) * SR)
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(3)

    def add(t0, sig, a):
        i = int(t0 * SR)
        j = min(n, i + len(sig))
        if i < n:
            out[i:j] += a * sig[:j - i]

    t = _t(0.28)
    kick = (np.sin(2 * np.pi * np.cumsum(48 + 95 * np.exp(-t * 28)) / SR) * np.exp(-t * 11)).astype(np.float32)
    t = _t(0.16)
    noise = np.diff(rng.normal(size=len(t) + 1)).astype(np.float32)
    clap = noise * (np.exp(-t * 32) + 0.6 * np.exp(-np.maximum(0, t - 0.012) * 45) * (t > 0.012))
    clap /= float(np.max(np.abs(clap))) or 1.0
    t = _t(0.045)
    hat = np.diff(np.diff(rng.normal(size=len(t) + 2))).astype(np.float32) * np.exp(-t * 95)
    hat /= float(np.max(np.abs(hat))) or 1.0
    for b in range(bars):
        t0 = b * CHANT_BAR
        add(t0, kick, 1.0)
        add(t0 + 2 * CHANT_BEAT, kick, 0.85)
        add(t0 + CHANT_BEAT, clap, 0.45)
        add(t0 + 3 * CHANT_BEAT, clap, 0.45)
        for e in range(8):
            add(t0 + e * CHANT_BEAT / 2, hat, 0.16 if e % 2 else 0.08)
    out /= float(np.max(np.abs(out))) or 1.0
    return out * amp


def is_open(syl):
    """Задгай үе: эгшгээр төгссөн."""
    return syl[-1].lower() in VOWELS


def reviews(cfg):
    """Өмнө үзсэн бүх үсгийг видеоны эхэнд давтах эсэх (хуучин хичээлүүд: тийм, шинэ: settings.json-оор үгүй)."""
    return cfg.get("review_letters", True)


def letter_color(ch):
    c = ch.lower()
    if c in VOWELS:
        return C_VOWEL
    if c in SEMIVOWELS:
        return C_SEMI
    if c.isdigit():
        return C_NUM
    if c.isalpha():
        return C_CONS
    return C_INK


def cap(s):
    return s[:1].upper() + s[1:]


def dur(a):
    return len(a) / SR


@lru_cache(None)
def font(path, size):
    return ImageFont.truetype(path, max(4, int(size)))


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def ease_back(x):
    x = clamp(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def pop(t, start, length=0.45):
    return ease_back((t - start) / length) if t >= start else 0.0


# ----------------------------------------------------------------- дуу

def load_audio(path):
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(out, np.float32).copy()
    idx = np.where(np.abs(a) > 0.02)[0]
    if len(idx):
        a = a[max(0, idx[0] - int(0.04 * SR)): idx[-1] + int(0.10 * SR)]
    return a


CHIMEGE_URL = "https://api.chimege.com/v1.2/synthesize"
CHIMEGE_VOICES = ["FEMALE1v2", "FEMALE2v2", "FEMALE3v2", "FEMALE4v2", "FEMALE5v2",
                  "MALE1v2", "MALE2v2", "MALE3v2", "MALE4v2"]


def load_chimege_token():
    """Токеныг CHIMEGE_TOKEN орчны хувьсагч эсвэл .chimege_token файлаас уншина (git-д орохгүй)."""
    tok = os.environ.get("CHIMEGE_TOKEN", "").strip()
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chimege_token")
    if not tok and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            tok = f.read().strip()
    if not tok:
        sys.exit("Chimege токен олдсонгүй. .chimege_token файлд токеноо хадгална уу.")
    return tok


class TTS:
    """Дуу үүсгэгч. cfg["tts_provider"]: "chimege" эсвэл "edge" (Microsoft)."""

    def __init__(self, cfg, cache_dir):
        self.provider = cfg.get("tts_provider", "edge")
        self.cache = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.pending, self.mem, self.collect = set(), {}, True
        self.dry = os.environ.get("TTS_DRY") == "1"   # туршилт: дуугүй, API дуудахгүй
        if self.provider == "chimege":
            c = cfg.get("chimege", {})
            self.voice = c.get("voice", "FEMALE3v2")
            self.pitch = c.get("pitch", 1.0)
            self.rn = f"speed={c.get('speed_narration', 1.0)}"
            self.rr = f"speed={c.get('speed_reading', 0.85)}"
            self.token = None
        else:
            self.voice = cfg.get("voice", "mn-MN-YesuiNeural")
            self.rn = cfg.get("rate_narration", "-5%")
            self.rr = cfg.get("rate_reading", "-20%")

    def path(self, text, rate):
        if self.provider == "chimege":
            key = f"chimege|{self.voice}|{self.pitch}|{rate}|{text}"
            return os.path.join(self.cache, hashlib.sha1(key.encode()).hexdigest()[:16] + ".wav")
        h = hashlib.sha1(f"{self.voice}|{rate}|{text}".encode()).hexdigest()[:16]
        return os.path.join(self.cache, h + ".mp3")

    def _chimege_fetch(self, text, rate, out):
        import urllib.request
        import urllib.error
        headers = {"Content-Type": "plain/text", "Token": self.token, "voice-id": self.voice,
                   "speed": rate.split("=")[1], "pitch": str(self.pitch), "sample-rate": "22050"}
        req = urllib.request.Request(CHIMEGE_URL, data=text.encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            if e.code == 403:
                raise SystemExit(f"Chimege: токен буруу эсвэл эрх дууссан (403). {body}")
            if e.code == 400:
                raise SystemExit(f"Chimege: бичвэрийн алдаа (400) {text!r}: {body}")
            raise
        if not data.startswith(b"RIFF"):
            raise RuntimeError(f"Chimege: WAV биш хариу ирлээ: {data[:120]!r}")
        with open(out + ".tmp", "wb") as f:
            f.write(data)
        os.replace(out + ".tmp", out)

    def get(self, text, rate):
        if self.collect:
            self.pending.add((text, rate))
            return np.zeros(SR, np.float32)
        if self.dry:
            return np.zeros(int(max(0.5, 0.075 * len(text)) * SR), np.float32)
        key = (text, rate)
        if key not in self.mem:
            self.mem[key] = load_audio(self.path(text, rate))
        return self.mem[key]

    async def _gen(self, text, rate, sem):
        p = self.path(text, rate)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return
        async with sem:
            err = None
            for attempt in range(5):
                try:
                    if self.provider == "chimege":
                        await asyncio.to_thread(self._chimege_fetch, text, rate, p)
                    else:
                        await edge_tts.Communicate(text, self.voice, rate=rate).save(p + ".tmp")
                        os.replace(p + ".tmp", p)
                    return
                except SystemExit:
                    raise
                except Exception as e:  # сүлжээний түр алдаа, серверийн ачаалал (503)
                    err = e
                    await asyncio.sleep(2 + 2 * attempt)
            raise RuntimeError(f"TTS амжилтгүй: {text!r}: {err}")

    def generate_all(self):
        if self.dry:
            print(f"TTS_DRY: {len(self.pending)} дууг алгаслаа (дуугүй туршилт)")
            self.collect = False
            return
        todo = [(t, r) for t, r in sorted(self.pending)
                if not (os.path.exists(self.path(t, r)) and os.path.getsize(self.path(t, r)) > 0)]
        if self.provider == "chimege" and todo:
            self.token = self.token or load_chimege_token()
            calls = sum(max(1, -(-len(t) // 200)) for t, _ in todo)
            print(f"Chimege: {len(todo)} шинэ дуу, ойролцоогоор {calls} дуудалт ({calls * 8}₮)")
            too_long = [t for t, _ in todo if len(t) > 200]
            if too_long:
                sys.exit(f"Chimege: 200 тэмдэгтээс урт бичвэр байна: {too_long[0]!r}")

        async def run():
            sem = asyncio.Semaphore(3 if self.provider == "chimege" else 6)
            await asyncio.gather(*(self._gen(t, r, sem) for t, r in todo))
        print(f"Дуу бэлтгэж байна: {len(self.pending)} хэсэг ({len(todo)} шинэ)...")
        asyncio.run(run())
        self.collect = False


def _t(sec):
    return np.arange(int(sec * SR)) / SR


def sfx_pop():
    t = _t(0.09)
    f = 500 + 3500 * t
    return (0.22 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35)).astype(np.float32)


def sfx_ding():
    t = _t(0.9)
    s = (np.sin(2 * np.pi * 1046 * t) + 0.5 * np.sin(2 * np.pi * 1568 * t)
         + 0.25 * np.sin(2 * np.pi * 2093 * t)) * np.exp(-t * 5)
    return (0.13 * s).astype(np.float32)


def sfx_tick():
    t = _t(0.06)
    return (0.22 * np.sin(2 * np.pi * 1200 * t) * np.exp(-t * 70)).astype(np.float32)


def sfx_whoosh():
    rng = np.random.default_rng(1)
    n = int(0.45 * SR)
    noise = np.convolve(rng.normal(size=n), np.ones(30) / 30, mode="same")
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (0.5 * noise * env).astype(np.float32)


def sfx_fanfare():
    out = np.zeros(int(1.4 * SR), np.float32)
    for i, f in enumerate([523, 659, 784, 1046]):
        t = _t(0.9 if i == 3 else 0.35)
        s = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * 4)
        st = int(i * 0.14 * SR)
        out[st:st + len(s)] += 0.12 * s
    return out


SFX_POP, SFX_DING, SFX_TICK = sfx_pop(), sfx_ding(), sfx_tick()
SFX_WHOOSH, SFX_FANFARE = sfx_whoosh(), sfx_fanfare()


# ----------------------------------------------------------------- зураг

def make_bg():
    top, bot = np.array([255, 247, 226], float), np.array([224, 240, 255], float)
    y = np.linspace(0, 1, H)[:, None, None]
    arr = np.broadcast_to(top * (1 - y) + bot * y, (H, W, 3)).astype(np.uint8)
    im = Image.fromarray(arr.copy()).convert("RGBA")
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rng = random.Random(7)
    cols = [(255, 190, 120), (140, 200, 255), (255, 160, 190), (160, 220, 150), (255, 225, 120)]
    for _ in range(16):
        r = rng.randint(30, 110)
        x, y0 = rng.randint(-40, W + 40), rng.randint(-40, H + 40)
        if 200 < x < W - 200 and 140 < y0 < H - 100:
            continue  # голыг цэвэрхэн үлдээнэ
        c = rng.choice(cols)
        d.ellipse([x - r, y0 - r, x + r, y0 + r], fill=c + (45,))
    return Image.alpha_composite(im, ov).convert("RGB")


@lru_cache(None)
def emoji_base(e):
    f = font(F_EMOJI, 160)
    im = Image.new("RGBA", (len(e) * 260 + 120, 320), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((30, 50), e, font=f, embedded_color=True)
    return im.crop(im.getbbox())


@lru_cache(4096)
def emoji_sized(e, h):
    b = emoji_base(e)
    w = max(1, int(b.width * h / b.height))
    return b.resize((w, h), Image.LANCZOS if h < 200 else Image.BILINEAR)


def paste_emoji(fr, e, cx, cy, height):
    h = int(height)
    if not e or h < 4:
        return
    im = emoji_sized(e, h)
    fr.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


def draw_text_center(d, text, cx, cy, size, fill, path=F_HEAD, stroke=0, stroke_fill=None):
    if size < 4:
        return
    f = font(path, size)
    l, t, r, b = f.getbbox(text, anchor="ls")
    d.text((cx - (l + r) / 2, cy - (t + b) / 2), text, font=f, fill=fill, anchor="ls",
           stroke_width=int(stroke), stroke_fill=stroke_fill)


def word_width(word, size, path=F_TEXT):
    return font(path, size).getlength(word)


def draw_word(d, word, cx, cy, size, hl=(), hl_color=C_HL, arcs=(), color=None, path=F_TEXT, ref=None,
              char_colors=None):
    """Үгийг үсэг бүрийг өнгөөр нь зурна. hl/arcs - (эхлэл, төгсгөл) индексийн жагсаалт."""
    if size < 6:
        return
    f = font(path, size)
    if not ref:
        ref = "0" if not any(c.isalpha() for c in word) else "Ам" if any(c.isupper() for c in word) else "ам"
    _, t, _, b = f.getbbox(ref, anchor="ls")
    base = cy - (t + b) / 2
    xh = -f.getbbox("а", anchor="ls")[1]
    x0 = cx - f.getlength(word) / 2
    xs = [x0 + f.getlength(word[:i]) for i in range(len(word) + 1)]
    pad = size * 0.07
    desc = any(c in DESCENDERS for c in word)   # р, у гэх мэт доошоо унжсан үсэг
    low = size * (0.30 if desc else 0.12)
    for s, e in hl:
        d.rounded_rectangle([xs[s] - pad, base - xh * 1.9, xs[e] + pad, base + low],
                            radius=int(size * 0.16), fill=hl_color)
    for i, ch in enumerate(word):
        fill = char_colors[i] if char_colors else color or letter_color(ch)
        d.text((xs[i], base), ch, font=f, fill=fill, anchor="ls")
    for s, e in arcs:
        sh = size * 0.16 if desc else 0
        d.arc([xs[s] + pad * 0.2, base - size * 0.10 + sh, xs[e] - pad * 0.2, base + size * 0.30 + sh],
              15, 165, fill=(95, 95, 120), width=max(3, int(size / 28)))


def draw_tile(d, text, cx, cy, w, h, scale=1.0, fill=C_WHITE, border=(232, 214, 186),
              text_size=None, hl=(), arcs=(), color=None):
    if scale <= 0.03:
        return
    w, h = w * scale, h * scale
    r = int(min(w, h) * 0.2)
    d.rounded_rectangle([cx - w / 2 + 5, cy - h / 2 + 9, cx + w / 2 + 5, cy + h / 2 + 9], r, fill=C_SHADOW)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], r, fill=fill,
                        outline=border, width=max(2, int(5 * scale)))
    ts = (text_size or h * 0.6 / scale) * scale
    draw_word(d, text, cx, cy - (h * 0.05 if arcs else 0), ts, hl=hl, arcs=arcs, color=color)


def grid(n, cy, cell, gap, maxrow=10):
    rows = [list(range(i, min(n, i + maxrow))) for i in range(0, n, maxrow)]
    pos = []
    y0 = cy - (len(rows) * cell + (len(rows) - 1) * gap) / 2 + cell / 2
    for ri, row in enumerate(rows):
        x0 = W / 2 - (len(row) * cell + (len(row) - 1) * gap) / 2 + cell / 2
        pos += [(x0 + j * (cell + gap), y0 + ri * (cell + gap)) for j in range(len(row))]
    return pos


def type_pill(fr, d, open_, cx, cy, scale=1.0):
    """Үеийн төрөл: 🔓 задгай (ногоон) / 🔒 битүү (ягаан)."""
    if scale <= 0.05:
        return
    text = "задгай" if open_ else "битүү"
    size = 40 * scale
    f = font(F_HEAD, size)
    w = f.getlength(text) + size * 2.6
    h = size * 1.7
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], int(h / 2),
                        fill=C_OPEN if open_ else C_CLOSED)
    paste_emoji(fr, "🔓" if open_ else "🔒", cx - w / 2 + size * 1.05, cy, size * 1.15)
    d.text((cx - w / 2 + size * 1.95, cy), text, font=f, fill=C_WHITE, anchor="lm")


def draw_your_turn(fr, t, t0, t1):
    """Хүүхдэд давтах ээлж ирснийг харуулна."""
    if t0 <= t < t1:
        s = pop(t, t0, 0.35) * (1 + 0.07 * math.sin(2 * math.pi * 1.8 * (t - t0)))
        paste_emoji(fr, "🗣️", W - 105, H - 95, 95 * s)


# ----------------------------------------------------------------- цагийн шугам

class Timeline:
    def __init__(self):
        self.scenes, self.sounds, self.t, self.section = [], [], 0.0, None

    def sound(self, local, samples):
        self.sounds.append((self.t + local, samples))

    def add(self, length, draw, overlay=True):
        self.scenes.append((self.t, length, draw, overlay, self.section))
        self.t += length


class Lesson:
    def __init__(self, cfg, tts):
        self.cfg, self.tts = cfg, tts
        self.letters = cfg["letters"]
        self.new = cfg.get("new_letters", "")
        self.rn, self.rr = tts.rn, tts.rr
        self.extra = cfg.get("repeat_extra", 0.0)   # хүүхэд давтах нэмэлт хугацаа (сек)
        self.tl = Timeline()
        self.chapters = [(0.0, "Эхлэл")]

    def say(self, text):
        return self.tts.get(text, self.rn)

    def read(self, text):
        return self.tts.get(text, self.rr)

    # -- хэсгүүд --------------------------------------------------------
    def intro(self):
        tl, cfg = self.tl, self.cfg
        narr = self.say(cfg["intro"])
        shown = self.letters if reviews(cfg) else (self.new or self.letters)
        topic = cfg.get("topic") if not self.new else None
        if topic and cfg.get("thumb_tiles"):
            shown = cfg["thumb_tiles"]
        n = len(shown)
        big = n <= 3   # цөөн үсэг: том харуулна
        t_l, step = 1.3, 0.32
        tl.sound(0.1, SFX_WHOOSH)
        tl.sound(0.7, narr)
        for i in range(n):
            tl.sound(t_l + i * step, SFX_POP)
        length = max(0.7 + dur(narr), t_l + n * step) + 1.2
        pos = grid(n, 500, 200 if big else 112, 30 if big else 18)
        title = cfg.get("title", "Уншиж сурцгаая!")
        num = cfg.get("lesson_number")

        def draw(fr, d, t):
            s = pop(t, 0.1, 0.6)
            draw_text_center(d, title, W / 2, 205, 90 * s, (255, 112, 40), stroke=9 * s, stroke_fill=C_WHITE)
            paste_emoji(fr, "📚", W / 2 - 520, 205, 110 * pop(t, 0.4))
            paste_emoji(fr, "✏️", W / 2 + 520, 205, 110 * pop(t, 0.5))
            if num:
                draw_text_center(d, f"{num}-р хичээл" + (f": {topic}" if topic else ""), W / 2, 320,
                                 44 * pop(t, 0.6), C_INK)
            for i, ch in enumerate(shown):
                sc = pop(t, t_l + i * step)
                x, y = pos[i]
                if big:
                    draw_tile(d, ch if topic else ch.upper() + ch, x, y, 260, 210, scale=sc, text_size=130,
                              fill=(255, 244, 196))
                else:
                    draw_tile(d, ch, x, y, 104, 104, scale=sc, text_size=70,
                              fill=(255, 244, 196) if ch in self.new else C_WHITE)
        tl.add(length, draw, overlay=False)

    def section(self, key):
        tl = self.tl
        sec = self.cfg["sections"][key]
        if key == "letters" and not reviews(self.cfg):
            sec = {**NEW_LETTER_SECTION, **self.cfg["sections"].get("new_letter", {})}
        self.chapters.append((tl.t, sec["title"]))
        tl.section = (sec["title"], SECTION_COLORS.get(key, (100, 100, 100)))
        narr = self.say(sec["say"])
        tl.sound(0.0, SFX_WHOOSH)
        tl.sound(0.6, narr)
        length = 0.6 + dur(narr) + 0.7
        color = SECTION_COLORS.get(key, (100, 100, 100))

        def draw(fr, d, t):
            p = ease_out(t / 0.5)
            bw = W * 0.86 * p
            if bw > 20:
                d.rounded_rectangle([W / 2 - bw / 2 + 6, 290 + 10, W / 2 + bw / 2 + 6, 480 + 10], 60, fill=C_SHADOW)
                d.rounded_rectangle([W / 2 - bw / 2, 290, W / 2 + bw / 2, 480], 60, fill=color)
            draw_text_center(d, sec["title"], W / 2, 385, 96 * pop(t, 0.25, 0.5), C_WHITE)
            paste_emoji(fr, sec.get("emoji", ""), W / 2, 175, 140 * pop(t, 0.45))
        tl.add(length, draw, overlay=False)

    def letter(self, ch):
        tl = self.tl
        info = self.cfg.get("letter_info", {}).get(ch, {})
        is_new = ch in self.new
        say = self.say(info.get("say", f"{ch.upper()} үсэг."))
        t_say = 0.55
        tl.sound(0.05, SFX_POP)
        tl.sound(t_say, say)
        t = t_say + dur(say) + 0.45
        ex = info.get("example")
        emoji = info.get("emoji")
        t_ex = None
        if ex:
            t_ex = t
            a = self.read(cap(ex) + ".")
            tl.sound(t_ex, SFX_POP)
            tl.sound(t_ex + 0.35, a)
            t = t_ex + 0.35 + dur(a)
        length = t + 1.6 + self.extra
        t_turn = t + 0.1
        cx = 400 if ex else W / 2
        hl = [(i, i + 1) for i, c in enumerate(ex or "") if c == ch]
        ex_colors = ([letter_color(c) if c.lower() in self.letters else C_DIM for c in ex]
                     if ex and info.get("listen") else None)

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            if t_say <= tt <= t_say + dur(say):
                s *= 1 + 0.035 * math.sin(2 * math.pi * 2.2 * (tt - t_say))
            draw_tile(d, ch.upper() + ch, cx, 395, 330, 300, scale=s, text_size=190)
            if is_new:
                sb = pop(tt, 0.35)
                if sb > 0:
                    bx, by = cx + 120, 230
                    d.rounded_rectangle([bx - 105 * sb, by - 32 * sb, bx + 105 * sb, by + 32 * sb],
                                        int(32 * sb), fill=(255, 90, 90))
                    draw_text_center(d, "Шинэ үсэг", bx + 14 * sb, by, 32 * sb, C_WHITE)
                    paste_emoji(fr, "⭐", bx - 95 * sb, by - 5, 58 * sb)
            if ex:
                se = pop(tt, t_ex)
                paste_emoji(fr, emoji, 900, 285, 170 * se)
                draw_word(d, ex, 900, 495 if emoji else 400, min(130, 520 / max(1, len(ex)) * 1.6) * se,
                          hl=hl, char_colors=ex_colors)
            draw_your_turn(fr, tt, t_turn, length)
        tl.add(length, draw)

    def syllable_groups(self):
        vow = [c for c in self.letters if c in VOWELS]
        cons = [c for c in self.letters if c not in VOWELS and c not in SEMIVOWELS]
        focus = self.cfg.get("syllable_consonants")
        if focus:
            cons = [c for c in cons if c in focus]
        vfocus = self.cfg.get("syllable_vowels")   # шинэ эгшиг: мо со ро хо / ом ос ор ох
        if vfocus:
            vow = [v for v in vow if v in vfocus]
            return [g for g in [[c + v for c in cons] for v in vow] + [[v + c for c in cons] for v in vow] if g]
        groups = [[c + v for v in vow] for c in cons]
        groups += [[v + c for v in vow] for c in cons]
        if "й" in self.letters:
            groups.append([v + "й" for v in vow if v in "аэиыоуөү"])
        return [g for g in groups if g]

    def syllable(self, syl, group, idx):
        tl = self.tl
        a = self.read(cap(syl) + ".")
        t_join, t_say = 0.55, 0.72
        t_end = t_say + dur(a)
        length = t_end + 1.5 + self.extra
        tl.sound(t_join - 0.03, SFX_POP)
        tl.sound(t_say, a)

        def draw(fr, d, t):
            cy = 320
            if t < t_join:
                p = ease_in_out(t / t_join)
                off = 100 + 240 * (1 - p)
                draw_tile(d, syl[0], W / 2 - off, cy, 190, 220, text_size=150)
                draw_tile(d, syl[1], W / 2 + off, cy, 190, 220, text_size=150)
                draw_text_center(d, "+", W / 2, cy, 90 * (1 - p), C_INK)
            else:
                k = t - t_join
                s = 1 + 0.10 * math.sin(min(1.0, k / 0.35) * math.pi)
                speaking = t_say <= t <= t_end + 0.2
                draw_tile(d, syl, W / 2, cy, 400, 220, scale=s, text_size=150,
                          fill=(255, 246, 200) if speaking else C_WHITE, arcs=[(0, len(syl))])
            # бүлгийн мөр
            gc = min(140, (W - 300) / len(group) - 22)   # олон эгшигтэй бол багтаана
            gs = 62 * gc / 140
            for j, (x, y) in enumerate(grid(len(group), 590, gc, 22)):
                if j < idx:
                    draw_tile(d, group[j], x, y, gc, 92, text_size=gs)
                elif j == idx:
                    draw_tile(d, group[j], x, y, gc, 92, text_size=gs, fill=C_HL, border=(240, 190, 60))
                else:
                    draw_tile(d, group[j], x, y, gc, 92, text_size=gs, fill=(244, 244, 246),
                              border=(225, 225, 230), color=C_GRAY)
            draw_your_turn(fr, t, t_end + 0.15, length)
        tl.add(length, draw)

    def syllable_row(self, group):
        tl = self.tl
        t = 0.5
        steps = []
        for syl in group:
            a = self.read(cap(syl) + ".")
            tl.sound(t, a)
            steps.append((t, t + dur(a) + 0.2))
            t += dur(a) + 0.3
        length = t + 1.7 + self.extra
        cell = min(230, (W - 160) / len(group) - 24)
        pos = grid(len(group), 360, cell, 24, maxrow=8)

        def draw(fr, d, tt):
            for j, (x, y) in enumerate(pos):
                active = steps[j][0] <= tt < steps[j][1]
                done = tt >= steps[j][0]
                s = pop(tt, 0.05 + j * 0.06) * (1.08 if active else 1.0)
                draw_tile(d, group[j], x, y, cell, cell * 0.9, scale=s, text_size=cell * 0.5,
                          fill=C_HL if active else C_WHITE, arcs=[(0, len(group[j]))] if done else ())
            draw_your_turn(fr, tt, t + 0.1, length)
        tl.add(length, draw)

    def word(self, w):
        tl = self.tl
        word = w["w"]
        syl = w.get("syl") or [word]
        emoji = w.get("emoji")
        ranges, p = [], 0
        for sy in syl:
            ranges.append((p, p + len(sy)))
            p += len(sy)
        assert "".join(syl) == word, f"Үеийн хуваалт буруу: {word} {syl}"
        tl.sound(0.05, SFX_POP)
        t = 0.75
        steps = []
        if len(syl) == 1:
            for i in range(len(word)):
                steps.append((t, t + 0.48, [(i, i + 1)], []))
                t += 0.5
            t += 0.15
        else:
            for k, (r, sy) in enumerate(zip(ranges, syl)):
                a = self.read(cap(sy) + ".")
                tl.sound(t, a)
                steps.append((t, t + dur(a) + 0.3, [r], ranges[:k + 1]))
                t += dur(a) + 0.4
        t_word = t
        aw = self.read(cap(word) + ".")
        tl.sound(t_word, aw)
        if emoji:
            tl.sound(t_word, SFX_POP)
        t = t_word + dur(aw)
        if w.get("explain"):
            t += 0.5
            ae = self.say(w["explain"])
            tl.sound(t, ae)
            t += dur(ae)
        length = t + 1.6 + self.extra
        t_turn = t_word + dur(aw) + 0.1
        size = min(220, (W - 200) / max(1, len(word)) * 1.6)
        cy = 475 if emoji else 380
        types = self.cfg.get("word_syl_types")
        if types and len(syl) > 1:
            size = min(size, 190)
            cy = 430 if emoji else 360

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            hl, arcs, col = [], [], C_HL
            for st, en, h, a in steps:
                if st <= tt < en:
                    hl = h
                if tt >= st:
                    arcs = a
            if tt >= t_word:
                hl, arcs, col = [(0, len(word))], ranges, C_OK
            draw_word(d, word, W / 2, cy, size * s, hl=hl, hl_color=col, arcs=arcs)
            if types and len(syl) > 1:   # үе бүрийн доор задгай 🔓 / битүү 🔒
                f = font(F_TEXT, size * s)
                x0 = W / 2 - f.getlength(word) / 2
                for k, (a, b) in enumerate(ranges):
                    if tt >= steps[k][0] + 0.25:
                        xc = x0 + f.getlength(word[:a]) + f.getlength(word[a:b]) / 2
                        sc = pop(tt, steps[k][0] + 0.25, 0.35)
                        type_pill(fr, d, is_open(syl[k]), xc, cy + size * 0.62 + 40, 0.8 * sc)
            if emoji:
                paste_emoji(fr, emoji, W / 2, 175, 150 * pop(tt, t_word))
            draw_your_turn(fr, tt, t_turn, length)
        tl.add(length, draw)

    def listen_word(self, w):
        """Сонсоод ол: үгийг уншаад, шинэ үсгийг нь нэг нэгээр тодруулна. Бусад үсэг саарал."""
        tl = self.tl
        word, emoji = w["w"], w.get("emoji")
        target = set(self.new.lower())
        idx = [i for i, c in enumerate(word) if c.lower() in target]
        tl.sound(0.05, SFX_POP)
        aw = self.read(cap(word) + ".")
        t_word = 0.6
        tl.sound(t_word, aw)
        t = t_word + dur(aw) + 0.5
        steps = []
        for i in idx:
            a = self.read(cap(word[i].lower()) + ".")
            tl.sound(t, SFX_POP)
            tl.sound(t + 0.1, a)
            steps.append(t)
            t += 0.1 + dur(a) + 0.3
        t += 0.2
        t_again = t
        tl.sound(t_again, aw)
        t = t_again + dur(aw)
        if w.get("explain"):
            t += 0.5
            ae = self.say(w["explain"])
            tl.sound(t, ae)
            t += dur(ae)
        length = t + 1.6 + self.extra
        t_turn = t_again + dur(aw) + 0.1
        size = min(210, (W - 200) / max(1, len(word)) * 1.6)
        cy = 480 if emoji else 380

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            lit = {i for k, i in enumerate(idx) if tt >= steps[k]}
            cur = [(i, i + 1) for k, i in enumerate(idx) if steps[k] <= tt < steps[k] + 0.7]
            again = t_again <= tt < t_again + dur(aw) + 0.2
            colors = [letter_color(c) if i in lit else C_DIM for i, c in enumerate(word)]
            draw_word(d, word, W / 2, cy, size * s, hl=cur or ([(0, len(word))] if again else []),
                      hl_color=C_HL if cur else C_OK, char_colors=colors)
            if emoji:
                paste_emoji(fr, emoji, W / 2, 190, 150 * pop(tt, 0.1))
            draw_your_turn(fr, tt, t_turn, length)
        tl.add(length, draw)

    def sentence(self, sd):
        tl = self.tl
        text = sd["s"]
        toks = text.split(" ")
        cleans = [tk.strip(",.!?") for tk in toks]
        t = 0.75
        steps = []
        tl.sound(0.05, SFX_POP)
        for i, c in enumerate(cleans):
            a = self.read(cap(c) + ".")
            tl.sound(t, a)
            steps.append((t, t + dur(a) + 0.25, i))
            t += dur(a) + 0.4
        t += 0.3
        t_full = t
        af = self.read(text)
        tl.sound(t_full, af)
        if sd.get("emoji"):
            tl.sound(t_full, SFX_POP)
        t = t_full + dur(af)
        length = t + 2.0 + self.extra
        size = 140
        sp = font(F_TEXT, size).getlength(" ") * 1.4
        while sum(word_width(tk, size) for tk in toks) + sp * (len(toks) - 1) > W - 140:
            size -= 6
            sp = font(F_TEXT, size).getlength(" ") * 1.4
        widths = [word_width(tk, size) for tk in toks]
        x = W / 2 - (sum(widths) + sp * (len(toks) - 1)) / 2
        centers = []
        for wd in widths:
            centers.append(x + wd / 2)
            x += wd + sp
        cy = 460

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            if s <= 0.02:
                return
            cur = next((i for st, en, i in steps if st <= tt < en), None)
            for i, tk in enumerate(toks):
                c = cleans[i]
                st = tk.find(c)
                hl, col = [], C_HL
                if tt >= t_full:
                    hl, col = [(st, st + len(c))], C_OK
                elif cur == i:
                    hl = [(st, st + len(c))]
                draw_word(d, tk, W / 2 + (centers[i] - W / 2) * s, cy, size * s, hl=hl, hl_color=col, ref="Ам")
            paste_emoji(fr, sd.get("emoji"), W / 2, 220, 160 * pop(tt, t_full))
            draw_your_turn(fr, tt, t_full + dur(af) + 0.1, length)
        tl.add(length, draw)

    def quiz(self, word, idx, n):
        tl = self.tl
        t0, count = 0.7, 3
        for k in range(count):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + count
        aw = self.read(cap(word) + ".")
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, aw)
        length = t_rev + 0.15 + dur(aw) + 1.3 + self.extra / 2
        size = min(200, (W - 300) / max(1, len(word)) * 1.6)
        cw = max(560, word_width(word, size) + 160)

        def draw(fr, d, t):
            s = pop(t, 0.05, 0.5)
            ok = t >= t_rev
            draw_tile(d, "", W / 2, 360, cw, 270, scale=s, fill=C_OK if ok else C_WHITE)
            draw_word(d, word, W / 2, 360, size * s)
            if ok:
                paste_emoji(fr, "⭐", W / 2 + cw / 2 - 10, 235, 110 * pop(t, t_rev))
            elif t >= t0:
                k = t - t0
                num = count - int(k)
                frac = k - int(k)
                cx, cy, r = W / 2, 600, 52
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_WHITE, outline=(230, 230, 235), width=8)
                d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=(235, 70, 70), width=8)
                draw_text_center(d, str(num), cx, cy, 56 * (1 + 0.25 * max(0, 1 - frac * 4)), (235, 70, 70))
            # явц
            for j in range(n):
                x = W / 2 + (j - (n - 1) / 2) * 34
                fill = (235, 70, 70) if j < idx or (j == idx and ok) else (225, 225, 232)
                d.ellipse([x - 10, 680 - 10, x + 10, 680 + 10], fill=fill)
        tl.add(length, draw)

    # -- задгай, битүү үе ---------------------------------------------
    def type_word(self, syl):
        return self.say("Задгай." if is_open(syl) else "Битүү.")

    def syl_explain(self, syl):
        """Үеийг уншаад, сүүлийн үсгийг тодруулж, задгай/битүү гэдгийг тайлбарлана."""
        tl = self.tl
        op = is_open(syl)
        a = self.read(cap(syl) + ".")
        tl.sound(0.05, SFX_POP)
        tl.sound(0.55, a)
        t_hl = 0.55 + dur(a) + 0.4
        tl.sound(t_hl, SFX_POP)
        ex = self.say("Сүүлийн үсэг нь эгшиг. Энэ бол задгай үе." if op else
                      "Сүүлийн үсэг нь гийгүүлэгч. Энэ бол битүү үе.")
        tl.sound(t_hl + 0.2, ex)
        t_pill = t_hl + 0.2 + dur(ex) * 0.5
        t_again = t_hl + 0.2 + dur(ex) + 0.4
        tl.sound(t_again, a)
        length = t_again + dur(a) + 1.6 + self.extra
        last = (len(syl) - 1, len(syl))

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            hl = [last] if tt >= t_hl else []
            draw_tile(d, "", W / 2, 320, 420, 250, scale=s)
            draw_word(d, syl, W / 2, 320, 170 * s, hl=hl, hl_color=(205, 240, 200) if op else (255, 214, 226))
            if tt >= t_hl:   # сүүлийн үсгийг заах сум
                f = font(F_TEXT, 170)
                x = W / 2 - f.getlength(syl) / 2 + f.getlength(syl[:-1]) + f.getlength(syl[-1]) / 2
                paste_emoji(fr, "⬇️", x, 150, 70 * pop(tt, t_hl))
            type_pill(fr, d, op, W / 2, 545, pop(tt, t_pill, 0.4))
            draw_your_turn(fr, tt, t_again + dur(a) + 0.1, length)
        tl.add(length, draw)

    def syl_pair(self, o, c):
        """Задгай, битүү хоёр үеийг зэрэгцүүлнэ: са | ас."""
        tl = self.tl
        tl.sound(0.05, SFX_POP)
        t = 0.6
        marks = []
        for syl in (o, c):
            a = self.read(cap(syl) + ".")
            tl.sound(t, a)
            t += dur(a) + 0.3
            tw = self.type_word(syl)
            tl.sound(t, SFX_POP)
            tl.sound(t + 0.1, tw)
            marks.append(t)
            t += 0.1 + dur(tw) + 0.5
        length = t + 1.4 + self.extra
        xs = (W / 2 - 270, W / 2 + 270)

        def draw(fr, d, tt):
            for k, syl in enumerate((o, c)):
                op = is_open(syl)
                on = tt >= marks[k]
                draw_tile(d, "", xs[k], 330, 380, 240, scale=pop(tt, 0.05 + k * 0.1),
                          fill=(236, 250, 234) if (on and op) else (255, 236, 242) if on else C_WHITE)
                draw_word(d, syl, xs[k], 330, 160 * pop(tt, 0.05 + k * 0.1),
                          hl=[(len(syl) - 1, len(syl))] if on else [],
                          hl_color=(205, 240, 200) if op else (255, 214, 226))
                type_pill(fr, d, op, xs[k], 540, pop(tt, marks[k], 0.4))
            draw_text_center(d, "|", W / 2, 330, 120 * pop(tt, 0.2), C_GRAY)
            draw_your_turn(fr, tt, marks[-1] + 0.6, length)
        tl.add(length, draw)

    def syl_sort(self, syl, idx, n):
        """Асуулт: энэ үе задгай уу, битүү юу? 3 хүртэл хүлээгээд хариулна."""
        tl = self.tl
        op = is_open(syl)
        a = self.read(cap(syl) + ".")
        tl.sound(0.05, SFX_POP)
        tl.sound(0.5, a)
        t0 = 0.5 + dur(a) + 0.4
        for k in range(3):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + 3
        tw = self.type_word(syl)
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, tw)
        length = t_rev + 0.15 + dur(tw) + 1.3 + self.extra / 2
        opts = ((True, W / 2 - 230), (False, W / 2 + 230))

        def draw(fr, d, tt):
            s = pop(tt, 0.05, 0.5)
            ok = tt >= t_rev
            draw_tile(d, "", W / 2, 290, 400, 230, scale=s, fill=C_OK if ok else C_WHITE)
            draw_word(d, syl, W / 2, 290, 160 * s, hl=[(len(syl) - 1, len(syl))] if ok else [],
                      hl_color=(205, 240, 200) if op else (255, 214, 226))
            for o_, x in opts:
                right = o_ == op
                sc = pop(tt, 0.4) * (1.12 if ok and right else 0.88 if ok else 1)
                if ok and not right:
                    sc *= 0.9
                type_pill(fr, d, o_, x, 545, sc)
                if ok and right:
                    paste_emoji(fr, "⭐", x + 150, 505, 70 * pop(tt, t_rev))
            if not ok and tt >= t0:
                k = tt - t0
                num, frac = 3 - int(k), k - int(k)
                cx, cy, r = W - 120, 600, 50
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_WHITE, outline=(230, 230, 235), width=8)
                d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=(235, 70, 70), width=8)
                draw_text_center(d, str(num), cx, cy, 54 * (1 + 0.25 * max(0, 1 - frac * 4)), (235, 70, 70))
            for j in range(n):
                x = W / 2 + (j - (n - 1) / 2) * 34
                fill = (235, 70, 70) if j < idx or (j == idx and ok) else (225, 225, 232)
                d.ellipse([x - 10, 680 - 10, x + 10, 680 + 10], fill=fill)
        tl.add(length, draw)

    # -- өгүүллэг (эх уншлага) ------------------------------------------
    def story_pages(self, story, size=74, max_lines=4):
        """Урт өгүүллэгийг хуудсанд хуваана: хуудас бүр max_lines мөрөөс илүүгүй, өгүүлбэр тасрахгүй.
        Буцаах: ([(хуудасны layout, size)], өгүүлбэр -> хуудасны №)."""
        sents = story["sentences"]
        pages, cur = [], []
        for k in range(len(sents)):
            trial = {"sentences": [sents[i] for i in cur + [k]]}
            lay, _ = self.story_layout(trial, size)
            nlines = len({y for *_, y in lay})
            if cur and nlines > max_lines:
                pages.append(cur)
                cur = []
            cur.append(k)
        pages.append(cur)
        out, where = [], {}
        for pi, ks in enumerate(pages):
            lay, sz = self.story_layout({"sentences": [sents[k] for k in ks]}, size)
            lay = [(tk, ks[k], x, y) for tk, k, x, y in lay]   # жинхэнэ өгүүлбэрийн № руу буцаана
            out.append((lay, sz))
            for k in ks:
                where[k] = pi
        return out, where

    def story_layout(self, story, size=74):
        """Өгүүллэгийн бүх үгийг мөрөнд хуваарилна: [(текст, өгүүлбэрийн №, x төв, y)]."""
        f = font(F_TEXT, size)
        sp = f.getlength(" ") * 1.3
        maxw = W - 220
        lines, cur, wsum = [], [], 0
        for k, sd in enumerate(story["sentences"]):   # өгүүлбэрийг аль болох нэг мөрөнд багтаана
            words = [(tk, k, self.tok_width(tk, size)) for tk in sd["s"].split(" ")]
            sw = sum(w for *_, w in words) + sp * (len(words) - 1)
            if cur and wsum + sp + sw > maxw:
                lines.append(cur)
                cur, wsum = [], 0
            for tk, kk, w in words:
                if cur and wsum + sp + w > maxw:
                    lines.append(cur)
                    cur, wsum = [], 0
                wsum += (sp if cur else 0) + w
                cur.append((tk, kk, w))
        if cur:
            lines.append(cur)
        lh = size * 1.5
        y0 = 440 - (len(lines) - 1) * lh / 2
        out = []
        for li, ln in enumerate(lines):
            total = sum(w for *_, w in ln) + sp * (len(ln) - 1)
            x = W / 2 - total / 2
            for tk, k, w in ln:
                out.append((tk, k, x + w / 2, y0 + li * lh))
                x += w + sp
        return out, size

    @staticmethod
    def tok_width(tk, size):
        rb = rebus(tk)
        if rb:
            return size * 1.25 + (font(F_TEXT, size).getlength(rb[2]) if rb[2] else 0)
        return font(F_TEXT, size).getlength(tk)

    def draw_story(self, fr, d, story, lay, size, cur_sent, cur_word=None, done=(), green=()):
        """cur_sent: одоо уншиж буй өгүүлбэр (бусад нь бүдэг эсвэл энгийн). cur_word: тухайн өгүүлбэрийн үгийн №."""
        counts = {}
        for tk, k, x, y in lay:
            wi = counts.get(k, 0)
            counts[k] = wi + 1
            rb = rebus(tk)
            if rb:   # зурган үг: дүрс + цэг тэмдэг
                w = self.tok_width(tk, size)
                x0 = x - w / 2
                on = k in green or (k == cur_sent and cur_word == wi)
                if on:
                    d.rounded_rectangle([x0 - 6, y - size * 0.62, x0 + size * 1.25 + 6, y + size * 0.62],
                                        int(size * 0.18), fill=C_OK if k in green else C_HL)
                dim = not (k == cur_sent or k in done or k in green)
                paste_emoji(fr, rb[1], x0 + size * 0.62, y, size * (0.75 if dim else 1.0))
                if rb[2]:
                    draw_word(d, rb[2], x0 + size * 1.25 + font(F_TEXT, size).getlength(rb[2]) / 2, y, size,
                              ref="Ам", char_colors=[C_DIM] * len(rb[2]) if dim else None)
                continue
            c = tk.strip(",.!?:")
            st = tk.find(c)
            hl, col = [], C_HL
            if k in green:
                hl, col = [(st, st + len(c))], C_OK
            elif k == cur_sent and cur_word == wi:
                hl = [(st, st + len(c))]
            colors = None if (k == cur_sent or k in done or k in green) else [C_DIM] * len(tk)
            draw_word(d, tk, x, y, size, hl=hl, hl_color=col, ref="Ам", char_colors=colors)

    def story_title(self, story):
        tl = self.tl
        a = self.read(story["title"] + ".")
        tl.sound(0.1, SFX_WHOOSH)
        tl.sound(0.8, a)
        t_again = 0.8 + dur(a) + 0.5
        length = t_again + 1.8 + self.extra

        def draw(fr, d, tt):
            paste_emoji(fr, story.get("emoji", "📖"), W / 2, 230, 200 * pop(tt, 0.2, 0.6))
            hl = [(0, len(story["title"]))] if 0.8 <= tt < 0.8 + dur(a) + 0.2 else []
            draw_word(d, story["title"], W / 2, 470, 130 * pop(tt, 0.4, 0.5), hl=hl, ref="Ам")
            draw_your_turn(fr, tt, t_again, length)
        tl.add(length, draw)

    def story_sentence(self, story, k, pages, where):
        """Өгүүлбэрийг үг үгээр, дараа нь бүтнээр уншина. Бусад өгүүлбэр дэлгэц дээр харагдана."""
        tl = self.tl
        sd = story["sentences"][k]
        lay, size = pages[where[k]]
        toks = sd["s"].split(" ")
        t = 0.6
        steps = []
        for i, tk in enumerate(toks):
            rb = rebus(tk)
            a = self.read(cap(rb[0] if rb else tk.strip(",.!?:")) + ".")
            tl.sound(t, a)
            if rb:
                tl.sound(t - 0.05, SFX_POP)
            steps.append((t, t + dur(a) + 0.25, i))
            t += dur(a) + 0.4
        t += 0.2
        t_full = t
        af = self.read(plain(sd["s"]))
        tl.sound(t_full, af)
        tl.sound(t_full, SFX_POP)
        t = t_full + dur(af)
        length = t + 2.0 + self.extra

        def draw(fr, d, tt):
            cw = next((i for st, en, i in steps if st <= tt < en), None)
            green = (k,) if tt >= t_full else ()
            self.draw_story(fr, d, story, lay, size, k, cw, done=range(k), green=green)
            hop = abs(math.sin(math.pi * 2.0 * tt)) * 18 if 0.6 <= tt < t_full + dur(af) else 0
            paste_emoji(fr, sd.get("emoji"), W / 2, 150 - hop, 100 * pop(tt, 0.1))
            draw_your_turn(fr, tt, t_full + dur(af) + 0.1, length)
        tl.add(length, draw)

    def story_full(self, story, pages, where):
        """Өгүүллэгийг эхнээс нь бүтнээр уншина."""
        tl = self.tl
        intro = self.say("Одоо бүтнээр нь уншъя.")
        tl.sound(0.3, intro)
        t = 0.3 + dur(intro) + 0.4
        spans = []
        for sd in story["sentences"]:
            af = self.read(plain(sd["s"]))
            tl.sound(t, af)
            spans.append((t, t + dur(af) + 0.3))
            t += dur(af) + 0.55
        length = t + 1.6 + self.extra
        n = len(story["sentences"])

        def draw(fr, d, tt):
            cur = next((k for k, (st, en) in enumerate(spans) if st <= tt < en), None)
            if cur is None:   # өгүүлбэр хоорондын завсар: дараагийн өгүүлбэрийн хуудсыг харуулна
                nxt = next((k for k, (st, en) in enumerate(spans) if tt < st), n - 1)
                page = where[nxt]
            else:
                page = where[cur]
            lay, size = pages[page]
            done = range(n) if tt >= spans[-1][1] else range(cur or 0)
            self.draw_story(fr, d, story, lay, size, cur, None, done=done,
                            green=(cur,) if cur is not None else ())
            e = story["sentences"][cur]["emoji"] if cur is not None else story.get("emoji")
            paste_emoji(fr, e, W / 2, 150, 100)
        tl.add(length, draw)

    def question(self, q, idx, n):
        """Өгүүллэгийн агуулгаар асуулт: 3 зургаас зөвийг олно."""
        tl = self.tl
        a = self.say(q["q"])
        tl.sound(0.05, SFX_POP)
        tl.sound(0.5, a)
        t0 = 0.5 + dur(a) + 0.4
        for k in range(3):
            tl.sound(t0 + k, SFX_TICK)
        t_rev = t0 + 3
        ans = self.say(q["a"])
        tl.sound(t_rev, SFX_DING)
        tl.sound(t_rev + 0.15, ans)
        length = t_rev + 0.15 + dur(ans) + 1.4 + self.extra / 2
        opts = q["options"]
        xs = [W / 2 + (i - (len(opts) - 1) / 2) * 300 for i in range(len(opts))]

        def draw(fr, d, tt):
            ok = tt >= t_rev
            paste_emoji(fr, "🤔", W / 2, 165, 110 * pop(tt, 0.1))
            for i, e in enumerate(opts):
                right = i == q["answer"]
                sc = pop(tt, 0.3 + i * 0.1) * (1.08 if ok and right else 0.85 if ok else 1)
                draw_tile(d, "", xs[i], 400, 240, 240, scale=sc,
                          fill=C_OK if ok and right else (244, 244, 246) if ok else C_WHITE)
                paste_emoji(fr, e, xs[i], 400, 160 * sc)
                if ok and right:
                    paste_emoji(fr, "⭐", xs[i] + 110, 290, 76 * pop(tt, t_rev))
            if not ok and tt >= t0:
                k = tt - t0
                num, frac = 3 - int(k), k - int(k)
                cx, cy, r = W - 120, 600, 50
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C_WHITE, outline=(230, 230, 235), width=8)
                d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=(235, 70, 70), width=8)
                draw_text_center(d, str(num), cx, cy, 54 * (1 + 0.25 * max(0, 1 - frac * 4)), (235, 70, 70))
            for j in range(n):
                x = W / 2 + (j - (n - 1) / 2) * 34
                fill = (235, 70, 70) if j < idx or (j == idx and ok) else (225, 225, 232)
                d.ellipse([x - 10, 680 - 10, x + 10, 680 + 10], fill=fill)
        tl.add(length, draw)

    # -- дүрүүд, үгийн шид, хэмнэл -------------------------------------
    def characters(self, chars):
        """Өгүүллэгийн дүрүүд нэг нэгээрээ үсэрч гарч ирэн танилцуулна. Хүүхэд нэрийг давтана."""
        tl = self.tl
        t = 0.5
        marks = []
        for c in chars:
            tl.sound(t, SFX_POP)
            a = self.say(c["say"])
            tl.sound(t + 0.25, a)
            t_name = t + 0.25 + dur(a) + 0.3
            nm = self.read(c["name"] + ".")
            tl.sound(t_name, nm)
            marks.append((t, t_name, t_name + dur(nm)))
            t = t_name + dur(nm) + 1.4 + self.extra / 2
        length = t + 0.6
        n = len(chars)
        xs = [W / 2 + (i - (n - 1) / 2) * 360 for i in range(n)]

        def draw(fr, d, tt):
            for i, c in enumerate(chars):
                t0, tn, te = marks[i]
                sc = pop(tt, t0, 0.5)
                if sc <= 0:
                    continue
                talking = t0 <= tt < te + 0.3
                hop = abs(math.sin(math.pi * 2.4 * (tt - t0))) * 26 if talking else 0
                d.ellipse([xs[i] - 120 * sc, 450 - 18, xs[i] + 120 * sc, 450 + 18], fill=(222, 228, 240))
                paste_emoji(fr, c["emoji"], xs[i], 330 - hop, 210 * sc)
                hl = [(0, len(c["name"]))] if tn <= tt < te + 0.2 else []
                draw_word(d, c["name"], xs[i], 545, 84 * pop(tt, tn - 0.2, 0.4), hl=hl, ref="Ам")
                if te <= tt < te + 1.3:
                    paste_emoji(fr, "🗣️", xs[i] + 120, 470, 64 * pop(tt, te, 0.3))
        tl.add(length, draw)

    @staticmethod
    def _changed(old, new):
        """new үгийн аль үсэг шинээр орж ирснийг олно (жижиг, том үсэг ялгахгүй)."""
        sm = difflib.SequenceMatcher(None, old.lower(), new.lower())
        keep = set()
        for a, b, size in sm.get_matching_blocks():
            keep.update(range(b, b + size))
        return [i for i in range(len(new)) if i not in keep]

    def magic(self, chain):
        """Үгийн шид: үсэг нэмэх/солиход шинэ үг, шинэ зураг гарч ирнэ."""
        tl = self.tl
        tl.sound(0.05, SFX_POP)
        t = 0.6
        steps = []   # (эхлэх, үг, зураг, шинэ үсгүүд, нисэх эхлэл)
        a = self.read(cap(chain[0]["w"]) + ".")
        tl.sound(t, a)
        steps.append((0.0, chain[0]["w"], chain[0].get("emoji"), [], None))
        t += dur(a) + 0.6
        for j in range(1, len(chain)):
            old, new = chain[j - 1]["w"], chain[j]["w"]
            t_fly = t
            tl.sound(t_fly, SFX_WHOOSH)
            tl.sound(t_fly + 0.5, SFX_DING)
            a = self.read(cap(new) + ".")
            tl.sound(t_fly + 0.85, a)
            steps.append((t_fly, new, chain[j].get("emoji"), self._changed(old, new), t_fly))
            t = t_fly + 0.85 + dur(a) + 0.6
        length = t + 1.1 + self.extra
        size = 190

        def draw(fr, d, tt):
            k = max(i for i, st in enumerate(steps) if st[0] <= tt)
            _, word, emoji, changed, t_fly = steps[k]
            p = clamp((tt - t_fly) / 0.5) if t_fly is not None else 1.0
            f = font(F_TEXT, size)
            _, top, _, bot = f.getbbox("Ам", anchor="ls")
            base = 430 - (top + bot) / 2
            x0 = W / 2 - f.getlength(word) / 2
            glow = t_fly is not None and t_fly + 0.5 <= tt < t_fly + 2.0
            for i, ch in enumerate(word):
                x = x0 + f.getlength(word[:i])
                y = base
                if i in changed:
                    y = base - 260 * (1 - ease_out(p))
                    if glow:
                        d.rounded_rectangle([x - 6, base - size * 0.78, x + f.getlength(ch) + 6, base + size * 0.12],
                                            int(size * 0.14), fill=C_HL)
                d.text((x, y), ch, font=f, fill=letter_color(ch), anchor="ls")
            if t_fly is not None and t_fly + 0.45 <= tt < t_fly + 1.1:   # оч гялбаа
                q = (tt - t_fly - 0.45) / 0.65
                for ang in range(0, 360, 60):
                    r = 120 + 140 * q
                    paste_emoji(fr, "✨", W / 2 + r * math.cos(math.radians(ang)),
                                360 + 0.5 * r * math.sin(math.radians(ang)), 52 * (1 - q))
            if emoji:
                es = pop(tt, (t_fly + 0.55) if t_fly is not None else 0.1, 0.45)
                paste_emoji(fr, emoji, W / 2, 170, 140 * es)
            draw_your_turn(fr, tt, steps[-1][0] + 1.6, length)
        tl.add(length, draw)

    def chant(self, bars):
        """Хэмнэлээр хэлэх: хоолой нэг хэмжээнд хэлж, дараагийнхад хүүхэд давтана. Цохилт арын аятай давхцана."""
        tl = self.tl
        lead = (-tl.t) % CHANT_BAR + CHANT_BAR    # эхний цохилт арын аяны хэмжээн дээр буух
        nb = 2 * len(bars)
        tl.sound(lead, drum_loop(nb))
        for i in range(4):                        # тоолж оруулах: 4 тик
            tl.sound(lead - (4 - i) * CHANT_BEAT, SFX_TICK)
        for b, items in enumerate(bars):
            t0 = lead + 2 * b * CHANT_BAR
            for text, beat, span in items:
                a = self.read(cap(text) + ".")
                tl.sound(t0 + beat * CHANT_BEAT - 0.04, a)
        length = lead + nb * CHANT_BAR + 0.9

        def draw(fr, d, tt):
            lt = tt - lead
            if lt < 0:   # тоолж оруулах
                k = int((tt - (lead - 4 * CHANT_BEAT)) / CHANT_BEAT)
                draw_text_center(d, "Бэлэн үү?", W / 2, 260, 84 * pop(tt, 0.1), (255, 112, 40), stroke=7,
                                 stroke_fill=C_WHITE)
                paste_emoji(fr, "🥁", W / 2, 420, 150 * pop(tt, 0.2))
                if 0 <= k < 4:
                    draw_text_center(d, str(k + 1), W / 2, 590, 70, C_INK)
                return
            bi = min(nb - 1, int(lt // CHANT_BAR))
            voice = bi % 2 == 0
            items = bars[bi // 2]
            blt = lt - bi * CHANT_BAR
            beat = blt / CHANT_BEAT
            cur = int(beat)
            since = (beat - cur) * CHANT_BEAT
            bounce = 1 + 0.10 * math.exp(-since * 9)
            n = len(items)
            widths = [max(180, word_width(text, 86) + 70) for text, _, _ in items]
            gap = 30
            x = W / 2 - (sum(widths) + gap * (n - 1)) / 2
            for (text, b0, span), w in zip(items, widths):
                cx = x + w / 2
                x += w + gap
                on = b0 <= beat < b0 + span
                shown = (not voice) or beat >= b0 - 0.2
                sc = (pop(blt, b0 * CHANT_BEAT - 0.2, 0.3) if voice else 1.0) * (bounce if on else 1)
                if shown:
                    draw_tile(d, text, cx, 360, w, 170, scale=sc, text_size=86,
                              fill=(C_HL if voice else (176, 232, 170)) if on else C_WHITE)
            for i in range(4):
                cx = W / 2 - 90 + i * 60
                r = 20 * (1 + 0.25 * math.exp(-since * 8)) if i == cur else 12
                col = ((255, 112, 40) if voice else (63, 166, 90)) if i == cur else (210, 212, 222)
                d.ellipse([cx - r, 650 - r, cx + r, 650 + r], fill=col)
            if not voice:
                f = font(F_HEAD, 44)
                label = "Одоо чи!"
                tw = f.getlength(label)
                x0 = W / 2 - (tw + 90) / 2
                d.rounded_rectangle([x0, 540, x0 + tw + 90, 596], 28, fill=(63, 166, 90))
                paste_emoji(fr, "🗣️", x0 + 38, 568, 40)
                d.text((x0 + 70, 568), label, font=f, fill=C_WHITE, anchor="lm")
        tl.add(length, draw)

    def outro(self):
        tl, cfg = self.tl, self.cfg
        self.chapters.append((tl.t, "Төгсгөл"))
        narr = self.say(cfg["outro"])
        tl.sound(0.2, SFX_FANFARE)
        tl.sound(1.0, narr)
        length = 1.0 + dur(narr) + 2.2
        rng = random.Random(3)
        parts = [(rng.uniform(0, W), rng.uniform(-H, 0), rng.uniform(90, 200), rng.choice(["⭐", "🌟", "🎉", "🎈"]),
                  rng.randint(40, 80), rng.uniform(0, 6.28)) for _ in range(28)]

        def draw(fr, d, t):
            for x, y, v, e, sz, ph in parts:
                yy = (y + v * t) % (H + 200) - 100
                paste_emoji(fr, e, x + 30 * math.sin(t * 1.5 + ph), yy, sz)
            paste_emoji(fr, "🏆", W / 2, 230, 190 * pop(t, 0.3, 0.6))
            draw_text_center(d, cfg.get("outro_title", "Баярлалаа!"), W / 2, 450, 120 * pop(t, 0.6, 0.6),
                             (255, 112, 40), stroke=10, stroke_fill=C_WHITE)
        tl.add(length, draw, overlay=False)

    def build(self):
        cfg = self.cfg
        self.intro()
        shown = self.letters if reviews(cfg) else [c for c in self.letters if c in self.new]
        if shown:
            self.section("letters")
            for ch in shown:
                self.letter(ch)
        if cfg.get("listen_words"):
            self.section("listen")
            for w in cfg["listen_words"]:
                self.listen_word(w)
        groups = self.syllable_groups() if cfg.get("show_syllables", True) else []
        if groups:
            self.section("syllables")
            for g in groups:
                for i, s in enumerate(g):
                    self.syllable(s, g, i)
                self.syllable_row(g)
        st = cfg.get("syl_types")
        if st:
            self.section("syltype")
            for s in st.get("explain", []):
                self.syl_explain(s)
            for o, c in st.get("pairs", []):
                self.syl_pair(o, c)
            if st.get("sort"):
                self.section("sort")
                for i, s in enumerate(st["sort"]):
                    self.syl_sort(s, i, len(st["sort"]))
        if cfg.get("characters"):
            self.section("characters")
            self.characters(cfg["characters"])
        if cfg.get("magic"):
            self.section("magic")
            for chain in cfg["magic"]:
                self.magic(chain)
        if cfg.get("chant"):
            self.section("chant")
            self.chant(cfg["chant"])
        if cfg.get("words") and cfg.get("video_words", True):
            self.section("words")
            for w in cfg["words"]:
                self.word(w)
        if cfg.get("sentences"):
            self.section("sentences")
            for s in cfg["sentences"]:
                self.sentence(s)
        story = cfg.get("story")
        if story:
            self.section("story")
            pages, where = self.story_pages(story)
            self.story_title(story)
            for k in range(len(story["sentences"])):
                self.story_sentence(story, k, pages, where)
            self.story_full(story, pages, where)
        if cfg.get("questions"):
            self.section("questions")
            for i, q in enumerate(cfg["questions"]):
                self.question(q, i, len(cfg["questions"]))
        if cfg.get("quiz"):
            self.section("quiz")
            for i, w in enumerate(cfg["quiz"]):
                self.quiz(w, i, len(cfg["quiz"]))
        self.outro()
        return self.tl


def draw_overlay(fr, d, section, letters, new):
    """Баруун дээд буланд үзсэн үсэг (эсвэл тоо, тэмдэг). letters: мөр эсвэл жагсаалт."""
    toks = list(letters)
    room = W - 22 - (font(F_HEAD, 30).getlength(section[0]) + 110 if section else 60)
    for size in (34, 30, 26, 22):   # үсэг олон болоход жижигрүүлнэ
        gap = max(4, size // 4)
        f = font(F_TEXT, size)
        cells = [max(size * 1.3, f.getlength(tk) + size * 0.47) for tk in toks]
        if sum(cells) + (len(toks) - 1) * gap + 28 <= room:
            break
    else:   # багтахгүй бол зөвхөн шинэ үсгээ
        toks = [tk for tk in toks if tk in new] or toks[-1:]
        size, gap = 34, 8
        f = font(F_TEXT, size)
        cells = [max(44, f.getlength(tk) + 16) for tk in toks]
    x1 = W - 22
    x0 = x1 - (sum(cells) + (len(toks) - 1) * gap + 28)
    y0, y1 = 18, 76
    d.rounded_rectangle([x0, y0, x1, y1], 29, fill=C_WHITE, outline=(232, 222, 205), width=3)
    x = x0 + 14
    for tk, c in zip(toks, cells):
        cx = x + c / 2
        if tk in new:
            d.rounded_rectangle([cx - c / 2, y0 + 7, cx + c / 2, y0 + 51], 22, fill=(255, 236, 160))
        draw_word(d, tk, cx, (y0 + y1) / 2, size)
        x += c + gap
    if section:
        title, color = section
        f = font(F_HEAD, 30)
        tw = f.getlength(title)
        d.rounded_rectangle([22, 18, 22 + tw + 44, 76], 29, fill=color)
        draw_text_center(d, title, 22 + (tw + 44) / 2, 47, 30, C_WHITE)


# ----------------------------------------------------------------- шалгалт, гаргалт

def load_cfg(cfg_path):
    """settings.json (хоолой, хөгжим гэх мэт нийтлэг тохиргоо) + хичээлийн JSON. Хичээлийнх нь давуу."""
    base = {}
    sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            base = json.load(f)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    return {**base, **cfg}


def lesson_id(cfg_path):
    """lessons/ хавтсаас харьцангуй замаар давтагдашгүй нэр: lessons/1/mongol/h07.json -> 1-mongol-h07"""
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lessons")
    rel = os.path.relpath(os.path.abspath(cfg_path), base)
    if rel.startswith(".."):
        rel = os.path.basename(cfg_path)
    return os.path.splitext(rel)[0].replace("\\", "-").replace("/", "-")


def validate(cfg):
    if cfg.get("type") == "math":
        return
    ok = set(cfg["letters"])
    bad = []
    items = [w["w"] for w in cfg.get("words", [])] + [s["s"] for s in cfg.get("sentences", [])] + cfg.get("quiz", [])
    items += [i.get("example", "") for i in cfg.get("letter_info", {}).values() if not i.get("listen")]
    story = cfg.get("story") or {}
    items += [story.get("title", "")] + [plain(REBUS.sub("", sd["s"])) for sd in story.get("sentences", [])]
    items += [st["w"] for chain in cfg.get("magic", []) for st in chain]
    items += [x[0] for b in cfg.get("chant", []) for x in b] + [c["name"] for c in cfg.get("characters", [])]
    st = cfg.get("syl_types") or {}
    items += st.get("explain", []) + [x for p in st.get("pairs", []) for x in p] + st.get("sort", [])
    for it in items:
        extra = {c for c in it.lower() if c.isalpha() and c not in ok}
        if extra:
            bad.append(f"  '{it}': үзээгүй үсэг {''.join(sorted(extra))}")
    if bad:
        sys.exit("Уншуулах текстэд үзээгүй үсэг орсон байна:\n" + "\n".join(bad))


def _midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def make_music(seconds, bpm=100):
    """Хүүхдэд зориулсан хөгжилтэй арын ая (өөрөө нийлэгжүүлсэн, зохиогчийн эрхгүй).
    I-V-vi-IV (C-G-Am-F) хөг, маримба маягийн арпеджио, зөөлөн басс, шажигнуур, хонхон аялгуу."""
    beat = 60.0 / bpm
    bar = 4 * beat
    n = int((seconds + 2) * SR)
    out = np.zeros(n, np.float32)
    rng = np.random.default_rng(5)

    def add(t0, sig):
        i = int(t0 * SR)
        if i >= n:
            return
        j = min(n, i + len(sig))
        out[i:j] += sig[:j - i]

    def marimba(f, dur, amp):
        t = _t(dur)
        env = np.exp(-t * 7) * (1 - np.exp(-t * 300))
        return (amp * env * (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 20))).astype(np.float32)

    def bell(f, dur, amp):
        t = _t(dur)
        env = np.exp(-t * 3.5) * (1 - np.exp(-t * 400))
        return (amp * env * (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t * 6))).astype(np.float32)

    def bass(f, dur, amp):
        t = _t(dur)
        env = np.minimum(1, t * 40) * np.exp(-t * 2.5)
        return (amp * env * np.sin(2 * np.pi * f * t)).astype(np.float32)

    def shaker(amp):
        t = _t(0.07)
        noise = np.diff(rng.normal(size=len(t) + 1)).astype(np.float32)
        return (amp * noise * np.exp(-t * 60)).astype(np.float32)

    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]   # C G Am F
    arp = [0, 1, 2, 1, 0, 1, 2, 1]
    melodies = [[76, 74, 72, 74], [74, 71, 67, 71], [72, 76, 79, 76], [77, 76, 74, 72]]
    for b in range(int(seconds / bar) + 2):
        ch = chords[b % 4]
        t0 = b * bar
        for k in (0, 2):
            add(t0 + k * beat, bass(_midi(ch[0] - 24), beat * 1.8, 0.5))
        for e in range(8):
            add(t0 + e * beat / 2, marimba(_midi(ch[arp[e]]), 0.5, 0.16))
            if e % 2 == 1:
                add(t0 + e * beat / 2, shaker(0.05))
        if (b // 4) % 2 == 1:   # 4 хэмнэл тутамд аялгуу орж ирнэ
            for q, m in enumerate(melodies[b % 4]):
                add(t0 + q * beat, bell(_midi(m), beat * 1.5, 0.10))
    out = out[:int(seconds * SR)]
    out /= float(np.max(np.abs(out))) or 1.0
    fade = int(1.5 * SR)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out


def duck(music, voice, depth=0.7, thr=0.04):
    """Яриа гарах үед хөгжмийг намсгана (sidechain)."""
    blk = SR // 100
    nb = len(voice) // blk + 1
    padded = np.zeros(nb * blk, np.float32)
    padded[:len(voice)] = np.abs(voice)
    env = padded.reshape(nb, blk).max(axis=1)
    g = np.empty(nb, np.float32)
    cur = 0.0
    for i, e in enumerate(env):
        target = min(1.0, e / thr)
        cur = target if target > cur else cur * 0.97 + target * 0.03   # хурдан намсгаж, аажмаар өсгөнө
        g[i] = 1 - depth * cur
    gain = np.repeat(g, blk)[:len(music)]
    return music * gain


def write_wav(tl, path, music_vol=0.0):
    total = int((tl.t + 0.5) * SR)
    buf = np.zeros(total, np.float32)
    for at, s in tl.sounds:
        i = int(at * SR)
        j = min(total, i + len(s))
        buf[i:j] += s[:j - i]
    peak = float(np.max(np.abs(buf))) or 1.0
    buf *= min(1.0, 0.9 / peak)
    if music_vol > 0:
        buf += duck(make_music(total / SR), buf) * music_vol
        peak = float(np.max(np.abs(buf))) or 1.0
        buf *= min(1.0, 0.95 / peak)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((buf * 32767).astype(np.int16).tobytes())


WATERMARK = True


@lru_cache(None)
def watermark_img(k=1):
    """Видеоны зүүн доод буланд байх жижиг лого (сувгийн нэр). k - томруулах үржвэр."""
    text = BRAND
    f = font(F_HEAD, 24 * k)
    tw = int(f.getlength(text))
    w, h = 58 * k + tw + 20 * k, 52 * k
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], 26 * k, fill=(255, 255, 255, 185))
    d.rounded_rectangle([6 * k, 6 * k, 46 * k, 46 * k], 10 * k, fill=(43, 103, 216, 255))
    d.rounded_rectangle([9 * k, 9 * k, 43 * k, 43 * k], 8 * k, fill=(253, 254, 255, 255))
    draw_word(d, "С", 27 * k, 27 * k, 30 * k, ref="ам")
    d.text((56 * k, h / 2), text, font=f, fill=(43, 103, 216, 235), anchor="lm")
    return im


def frame_at(tl, bg, starts, t, letters, new):
    k = max(0, bisect.bisect_right(starts, t) - 1)
    st, _, draw, overlay, section = tl.scenes[k]
    fr = bg.copy()
    d = ImageDraw.Draw(fr)
    draw(fr, d, t - st)
    if overlay:
        draw_overlay(fr, d, section, letters, new)
    if WATERMARK:
        wm = watermark_img()
        fr.paste(wm, (20, H - wm.height - 18), wm)
    return fr


def make_thumbnail(cfg, bg, path):
    fr = bg.copy()
    d = ImageDraw.Draw(fr)
    draw_text_center(d, cfg.get("title", "Уншиж сурцгаая!"), W / 2, 205, 96, (255, 112, 40),
                     stroke=10, stroke_fill=C_WHITE)
    letters, new = overlay_tokens(cfg)
    tiles = cfg.get("thumb_tiles") if cfg.get("type") != "math" and not new else None
    if tiles:
        for i, (x, y) in enumerate(grid(len(tiles), 372, 300, 30)):
            draw_tile(d, tiles[i], x, y, 300, 230, text_size=150, fill=(255, 238, 160))
    elif cfg.get("type") != "math" and not reviews(cfg) and new:
        for i, (x, y) in enumerate(grid(len(new), 372, 300, 30)):
            draw_tile(d, new[i].upper() + new[i], x, y, 300, 230, text_size=165, fill=(255, 238, 160))
    else:
        cell = min(150, (W - 120) / len(letters) - 16)
        for i, (x, y) in enumerate(grid(len(letters), 385, cell, 16, maxrow=12)):
            ch = letters[i]
            draw_tile(d, ch, x, y, cell, cell * 1.1, text_size=cell * (0.6 if len(ch) > 1 else 0.75),
                      fill=(255, 238, 160) if ch in new else C_WHITE)
    num = cfg.get("lesson_number")
    if num:
        d.rounded_rectangle([60, 520, 470, 640], 60, fill=(33, 140, 230))
        draw_text_center(d, f"{num}-р хичээл", 265, 580, 64, C_WHITE)
    d.rounded_rectangle([W - 420, 520, W - 60, 640], 60, fill=(67, 170, 80))
    draw_text_center(d, f"{cfg.get('grade', 1)}-р анги", W - 240, 580, 64, C_WHITE)
    big = watermark_img(2)
    fr.paste(big, (int(W / 2 - big.width / 2), 22), big)
    paste_emoji(fr, cfg.get("thumb_emoji", "📚"), W / 2, 585, 150)
    fr.save(path)


def overlay_tokens(cfg):
    """Видео болон thumbnail дээр харуулах үсэг/тоо, шинээр нь тодруулах хэсэг."""
    if cfg.get("type") == "math":
        return [str(c) for c in cfg["chips"]], [str(c) for c in cfg.get("new_chips", [])]
    return list(cfg["letters"]), cfg.get("new_letters", "")


# Тайлбарын эхний мөр: «Хүүхдэд зориулсан» бичлэгт линк дарагддаггүй тул хялбар бичигдэх хаягийг дээр нь харуулна
DESC_TOP = "📒 Дасгал, тоглоом, бүх хичээл: suragch.cloud"

DESC_LINKS = [
    "Бусад хичээл: https://suragch.cloud/",
    "Facebook: https://www.facebook.com/profile.php?id=61596411881841",
    "Эцэг эх, том хүмүүс дэмжих бол: https://suragch.cloud/#/support",
]


def math_youtube(cfg, chap):
    num, grade = cfg.get("lesson_number", ""), cfg.get("grade", 1)
    title = f"{cfg.get('title', 'Тоолж сурцгаая!')} {num}-р хичээл: {cfg['topic']} | {grade}-р анги математик | {BRAND}"
    desc = "\n".join([
        DESC_TOP,
        "",
        f"{BRAND}: {grade}-р ангийн хүүхдэд зориулсан математикийн хичээл.",
        f"Сэдэв: {cfg['topic']}.",
        cfg.get("summary", ""),
        "",
        "Дэлгэцийн буланд 🗣️ тэмдэг гарахад хүүхэд чангаар давтаж хэлээрэй.",
        "Асуулт гарахад видеог зогсоолгүй, 3 хүртэл тоолох хооронд хариултаа хэлээрэй.",
        "",
        "Хичээлийн агуулга:",
        chap,
        "",
        *DESC_LINKS,
        "",
        f"#{BRAND.lower()} #математик #{grade}ранги #тоо #тоолох",
    ])
    tags = (f"{BRAND.lower()}, математик, тоо, тоолох, тоо тоолох, нэмэх, хасах, их бага, {grade}-р анги, "
            "нэгдүгээр анги, бага анги, хүүхдэд, хичээл, тоо сурах, " + cfg["topic"])
    return title, desc, tags


def write_youtube(cfg, chapters, name, root, bg):
    out = os.path.join(root, "youtube")
    os.makedirs(out, exist_ok=True)
    chap = "\n".join(f"{int(t // 60)}:{int(t % 60):02d} {n}" for t, n in chapters)
    if cfg.get("type") == "math":
        title, desc, tags = math_youtube(cfg, chap)
    else:
        title, desc, tags = reading_youtube(cfg, chap)
    thumb = os.path.join(out, f"{name}_thumbnail.png")
    make_thumbnail(cfg, bg, thumb)
    txt = "\n".join([
        "ГАРЧИГ (Title):", title, "",
        "ТАЙЛБАР (Description):", desc, "",
        "ШОШГО (Tags):", tags, "",
        "ТОХИРГОО:",
        f"- Thumbnail: {os.path.basename(thumb)}",
        "- Audience: Yes, it's made for kids (Хүүхдэд зориулсан)",
        "- Visibility: Public",
        "- Category: Education",
        "- Video language: Mongolian",
        "",
    ])
    p = os.path.join(out, f"{name}_youtube.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)
    print("YouTube:", p)


def reading_youtube(cfg, chap):
    letters = ", ".join(cfg["letters"])
    new = ", ".join(cfg.get("new_letters", "")) or "-"
    num = cfg.get("lesson_number", "")
    words = ", ".join(w["w"] for w in cfg.get("words", []))
    heard = ", ".join(w["w"] for w in cfg.get("listen_words", []))
    grade = cfg.get("grade", 1)
    title = f"Уншиж сурцгаая! {num}-р хичээл: {letters} үсэг | {grade}-р анги | {BRAND}"
    if not reviews(cfg):
        title = f"Уншиж сурцгаая! {num}-р хичээл: {new.upper()} үсэг | {grade}-р анги | {BRAND}"
    topic = cfg.get("topic") if not cfg.get("new_letters") else None
    if topic:
        title = f"Уншиж сурцгаая! {num}-р хичээл: {topic} | {grade}-р анги | {BRAND}"
    if len(title) > 100:  # YouTube-ийн хязгаар: үсэг олон болоход зөвхөн шинэ үсгээ бичнэ
        title = f"Уншиж сурцгаая! {num}-р хичээл: шинэ үсэг {new.upper()} | {grade}-р анги | {BRAND}"
    desc = "\n".join([
        DESC_TOP,
        "",
        f"{BRAND}: {grade}-р ангийн хүүхдэд зориулсан уншлагын хичээл.",
        (cfg.get("summary", "") if topic else
         f"{new.upper()} үсэгтэй танилцаж, үе холбож, үг, өгүүлбэр уншина." if cfg.get("words") and not reviews(cfg) else
         f"Үзсэн үсгүүдээ ({letters}) давтаж, үе холбож, үг, өгүүлбэр уншина." if cfg.get("words") else
         f"{new.upper()} үсэгтэй танилцаж, сонссон үгэн дотроос нь олж сурна."),
        f"Үзсэн үсгүүд: {letters}" if topic else f"Шинэ үсэг: {new}",
        "",
        "Дэлгэцийн буланд 🗣️ тэмдэг гарахад хүүхэд чангаар давтаж хэлээрэй.",
        "",
        "Хичээлийн агуулга:",
        chap,
        "",
        f"Унших үгс: {words}" if words else f"Сонсох үгс: {heard}",
        "",
        *DESC_LINKS,
        "",
        f"#{BRAND.lower()} #уншлага #{grade}ранги #монголхэл #цагаантолгой",
    ])
    tags = (f"{BRAND.lower()}, уншлага, уншиж сурах, цагаан толгой, монгол хэл, 1-р анги, нэгдүгээр анги, "
            "бага анги, үсэг, үе холбох, хүүхдэд, хичээл, "
            + (cfg.get("tags", topic) if topic else
               ", ".join(cfg["letters"] if reviews(cfg) else cfg.get("new_letters", "")) + " үсэг"))
    return title, desc, tags
    print("Thumbnail:", thumb)


def voice_samples():
    """Chimege-ийн бүх хоолойгоор жишээ бичлэг хийж samples/ хавтсанд хадгална."""
    root = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(root, "samples")
    os.makedirs(out, exist_ok=True)
    text = "Сайн байна уу, хүүхдүүдээ! Ма. Мэ. Ам. Эмээ. Ийм сам."
    for i, v in enumerate(CHIMEGE_VOICES, 1):
        tts = TTS({"tts_provider": "chimege", "chimege": {"voice": v}}, os.path.join(root, ".tts_cache"))
        tts.get(text, tts.rr)
        tts.generate_all()
        dst = os.path.join(out, f"{i}_{v}.mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tts.path(text, tts.rr), "-b:a", "96k", dst], check=True)
        print(dst)
    music = make_music(25.0) * 0.5
    wav = os.path.join(out, "music_preview.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((music * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-b:a", "128k", wav[:-4] + ".mp3"], check=True)
    os.remove(wav)
    print(wav[:-4] + ".mp3")


def lesson_class(cfg):
    if cfg.get("type") == "math":
        from make_math import MathLesson
        return MathLesson
    return Lesson


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if "--voices" in sys.argv:
        return voice_samples()
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cfg_path = sys.argv[1]
    snap = "--snap" in sys.argv
    if os.environ.get("TTS_DRY") == "1" and not snap:
        sys.exit("TTS_DRY=1 зөвхөн --snap (шалгах зураг)-тай ажиллана: дуугүй видео, буруу бүлгийн хугацаа гаргахгүйн тулд.")
    global WATERMARK
    WATERMARK = "--no-watermark" not in sys.argv
    cfg = load_cfg(cfg_path)
    validate(cfg)
    root = os.path.dirname(os.path.abspath(__file__))
    tts = TTS(cfg, os.path.join(root, ".tts_cache"))
    cls = lesson_class(cfg)
    cls(cfg, tts).build()             # 1-р алхам: хэрэгтэй дуунуудыг цуглуулна
    tts.generate_all()
    lesson = cls(cfg, tts)
    tl = lesson.build()               # 2-р алхам: жинхэнэ хугацаагаар
    letters, new = overlay_tokens(cfg)
    bg = make_bg()
    starts = [s[0] for s in tl.scenes]
    name = lesson_id(cfg_path)
    out_dir = os.path.join(root, "videos")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Үргэлжлэх хугацаа: {int(tl.t // 60)}:{int(tl.t % 60):02d}, {len(tl.scenes)} үзэгдэл")

    if "--youtube" in sys.argv:
        write_youtube(cfg, lesson.chapters, name, root, bg)
        return

    if snap:
        thumbs = []
        for st, ln, *_ in tl.scenes:
            thumbs.append(frame_at(tl, bg, starts, st + ln - 1.0, letters, new).resize((320, 180)))
        cols = 6
        for page in range(0, len(thumbs), 36):
            chunk = thumbs[page:page + 36]
            rows = math.ceil(len(chunk) / cols)
            sheet = Image.new("RGB", (cols * 324, rows * 184), (40, 40, 40))
            for i, th in enumerate(chunk):
                sheet.paste(th, ((i % cols) * 324 + 2, (i // cols) * 184 + 2))
            p = os.path.join(out_dir, f"{name}_snap{page // 36 + 1}.png")
            sheet.save(p)
            print("Зураг:", p)
        return

    wav = os.path.join(out_dir, f"{name}.wav")
    out = os.path.join(out_dir, f"{name}.mp4")
    write_wav(tl, wav, music_vol=cfg.get("music_volume", 0.16))
    n = int(math.ceil(tl.t * FPS))
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(frame_at(tl, bg, starts, i / FPS, letters, new).tobytes())
        if i % 500 == 0:
            print(f"  {i}/{n} кадр", flush=True)
    proc.stdin.close()
    proc.wait()
    os.remove(wav)
    if proc.returncode:
        sys.exit("ffmpeg алдаа гарлаа")
    print("Бэлэн:", out)


if __name__ == "__main__":
    main()
