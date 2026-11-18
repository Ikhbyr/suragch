#!/usr/bin/env python
"""Facebook хуудас руу хичээлийн бичлэгийг нийтэлнэ (Graph API).

Хэрэглээ:
    python fb.py setup     # .fb_setup.json-оос хугацаагүй Page token гаргаж .fb_token-д хадгална
    python fb.py check     # токен ажиллаж байгаа эсэх, хуудасны нэр
    python fb.py queue     # хуваарьт орсон постууд
    python fb.py pin       # бүх хичээлийн линктэй pin постыг үүсгэнэ/шинэчилнэ

Бичлэг хуудсанд шууд нийтлэгдэнэ. SCHEDULE = True болговол өдөрт 1 пост, орой 20:00 (Улаанбаатар) хуваарьтай болно.
Нийтэлсэн хичээлийн JSON-д "facebook_id" бичигдэх тул давхар нийтлэхгүй.
Токенууд (.fb_token, .fb_setup.json) git-д орохгүй, дэлгэцэнд хэвлэгдэхгүй.
"""
import datetime as dt
import json
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(ROOT, ".fb_token")
SETUP_FILE = os.path.join(ROOT, ".fb_setup.json")
API = "https://graph.facebook.com/v23.0"
VIDEO_API = "https://graph-video.facebook.com/v23.0"
TZ = dt.timezone(dt.timedelta(hours=8))   # Улаанбаатар
POST_HOUR = 20
SCHEDULE = False   # True: хуваарьтай (өдөрт 1, 20:00), False: шууд нийтэлнэ
SITE = "https://suragch.cloud/"
PIN_FILE = os.path.join(ROOT, "facebook_pin.json")   # pin постын id (нууц биш, git-д орно)


class FBError(Exception):
    pass


def _check(r):
    """Алдааны мессежийг токен хэвлэхгүйгээр гаргана."""
    try:
        data = r.json()
    except ValueError:
        raise FBError(f"HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400 or "error" in data:
        e = data.get("error", {})
        raise FBError(f"{e.get('type', 'Error')} ({e.get('code')}): {e.get('message', r.status_code)}")
    return data


def get(url, **params):
    try:
        return _check(requests.get(url, params=params, timeout=60))
    except requests.RequestException as e:   # URL-д токен байгаа тул бүтэн алдааг хэвлэхгүй
        raise FBError(f"Сүлжээний алдаа: {type(e).__name__}") from None


def load_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------ тохиргоо
def setup():
    if not os.path.exists(SETUP_FILE):
        sys.exit(f"{SETUP_FILE} олдсонгүй. README-ийн 'Facebook' хэсгийг харна уу.")
    with open(SETUP_FILE, encoding="utf-8") as f:
        s = json.load(f)
    missing = [k for k in ("app_id", "app_secret", "user_token") if not str(s.get(k, "")).strip()]
    if missing:
        sys.exit(f".fb_setup.json-д дутуу: {', '.join(missing)}")
    long_user = get(f"{API}/oauth/access_token", grant_type="fb_exchange_token", client_id=s["app_id"],
                    client_secret=s["app_secret"], fb_exchange_token=s["user_token"])["access_token"]
    pages = get(f"{API}/me/accounts", access_token=long_user, fields="id,name,access_token,tasks").get("data", [])
    if not pages:
        sys.exit("Хуудас олдсонгүй. Graph API Explorer дээр токен үүсгэхдээ хуудсаа сонгосон эсэхээ шалгана уу.")
    want = str(s.get("page_name", "")).strip()
    if len(pages) > 1 and not want:
        print("Хэд хэдэн хуудас олдлоо. .fb_setup.json-д \"page_name\" нэмнэ үү:")
        for p in pages:
            print("  -", p["name"])
        sys.exit(1)
    page = next((p for p in pages if not want or p["name"] == want), None)
    if not page:
        sys.exit(f"'{want}' нэртэй хуудас олдсонгүй: " + ", ".join(p["name"] for p in pages))
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"page_id": page["id"], "page_name": page["name"], "token": page["access_token"]}, f)
    # богино хугацааны токеныг файлаас арилгана (хэрэггүй болсон)
    s["user_token"] = ""
    with open(SETUP_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)
    print(f"Бэлэн: «{page['name']}» хуудасны токен хадгалагдлаа ({os.path.basename(TOKEN_FILE)}).")
    check()


def check():
    t = load_token()
    if not t:
        sys.exit("Facebook токен алга (.fb_token). Эхлээд: python fb.py setup")
    info = get(f"{API}/{t['page_id']}", fields="name,link,followers_count", access_token=t["token"])
    dbg = get(f"{API}/debug_token", input_token=t["token"], access_token=t["token"]).get("data", {})
    exp = dbg.get("expires_at", 0)
    print(f"Хуудас: {info['name']} ({info.get('link', '')})")
    print(f"Дагагч: {info.get('followers_count', '?')}")
    print("Токен: " + ("хугацаагүй" if not exp else dt.datetime.fromtimestamp(exp, TZ).strftime("%Y-%m-%d хүртэл")))
    print("Эрх: " + ", ".join(dbg.get("scopes", [])))


# ------------------------------------------------ хуваарь
def scheduled_times():
    """Хичээлүүдийн JSON-д бичигдсэн Facebook постын цагууд."""
    import glob
    out = []
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("facebook_time"):
            out.append(c["facebook_time"])
    return out


def next_slot():
    """Дараагийн чөлөөт 20:00. Facebook: дор хаяж 10 минутын дараа."""
    now = dt.datetime.now(TZ)
    t = now.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
    if t < now + dt.timedelta(minutes=20):
        t += dt.timedelta(days=1)
    taken = {dt.datetime.fromtimestamp(x, TZ).date() for x in scheduled_times() if x > now.timestamp()}
    while t.date() in taken:
        t += dt.timedelta(days=1)
    return t


def queue():
    now = dt.datetime.now(TZ).timestamp()
    import glob
    rows = []
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("facebook_time"):
            rows.append((c["facebook_time"], os.path.relpath(p, ROOT)))
    for ts, p in sorted(rows):
        state = "хүлээгдэж байна" if ts > now else "нийтлэгдсэн"
        print(dt.datetime.fromtimestamp(ts, TZ).strftime("%m-%d %H:%M"), state, p)


# ------------------------------------------------ нийтлэл
SUBJ = {"mongol": ("Монгол хэл", "монголхэл"), "math": ("Математик", "математик")}


def post_text(cfg, lesson_id, youtube_id):
    num, grade = cfg.get("lesson_number", ""), cfg.get("grade", 1)
    name, tag = SUBJ.get(cfg.get("subject", ""), (cfg.get("subject", ""), cfg.get("subject", "")))
    if cfg.get("type") == "math":
        head = f"{cfg.get('title', '')} {num}-р хичээл: {cfg['topic']}"
        what = cfg.get("summary", "")
    else:
        new = cfg.get("new_letters", "")
        if cfg.get("review_letters", True):
            head = f"{cfg.get('title', '')} {num}-р хичээл: {', '.join(cfg['letters'])} үсэг"
            what = f"Шинэ үсэг: {new.upper()}. Үсгээ давтаж, үе холбож, үг, өгүүлбэр уншина."
        else:
            head = f"{cfg.get('title', '')} {num}-р хичээл: {new.upper()} үсэг"
            what = f"{new.upper()} үсэгтэй танилцаж, үе холбож, үг, өгүүлбэр уншина."
    lines = [
        f"📒 {grade}-р анги, {name}",
        head,
        "",
        what,
        "",
        "Видеон дээр 🗣️ тэмдэг гарахад хүүхэд чангаар давтаж хэлээрэй.",
        "",
        f"🎮 Дасгал, тоглоом: {SITE}#/{lesson_id}",
        f"▶ YouTube: https://youtu.be/{youtube_id}" if youtube_id else "",
        "",
        f"#сурагч #{grade}ранги #{tag} #хүүхдэд",
    ]
    return "\n".join(l for l in lines if l is not None).replace("\n\n\n", "\n\n"), head


def post_lesson(path, mp4, thumb_png, when=None):
    """Бичлэгийг хуудсанд нийтэлнэ (шууд эсвэл хуваарьтай). (video_id, цаг) буцаана."""
    import make_lesson as M
    t = load_token()
    if not t:
        raise FBError("Facebook токен алга (.fb_token)")
    cfg = M.load_cfg(path)
    lid = M.lesson_id(path)
    desc, title = post_text(cfg, lid, cfg.get("youtube_id", ""))
    immediate = when is None and not SCHEDULE
    when = dt.datetime.now(TZ) if immediate else (when or next_slot())
    jpg = os.path.join(ROOT, ".tts_cache", f"fbthumb_{lid}.jpg")
    from PIL import Image
    Image.open(thumb_png).convert("RGB").save(jpg, quality=90)
    data = {"title": title, "description": desc, "access_token": t["token"]}
    if not immediate:
        data.update(published="false", scheduled_publish_time=str(int(when.timestamp())))
    try:
        with open(mp4, "rb") as v, open(jpg, "rb") as th:
            r = requests.post(f"{VIDEO_API}/{t['page_id']}/videos", data=data,
                              files={"source": (os.path.basename(mp4), v, "video/mp4"),
                                     "thumb": ("thumb.jpg", th, "image/jpeg")}, timeout=900)
    except requests.RequestException as e:
        raise FBError(f"Сүлжээний алдаа: {type(e).__name__}") from None
    finally:
        os.remove(jpg)
    vid = _check(r)["id"]
    set_fields(path, facebook_id=vid, facebook_time=int(when.timestamp()))
    return vid, when


def set_fields(path, **kv):
    """Хичээлийн JSON-д талбар нэмнэ/шинэчилнэ (бусад форматыг хадгална)."""
    s = open(path, encoding="utf-8").read()
    for k, v in kv.items():
        val = json.dumps(v, ensure_ascii=False)
        if f'"{k}"' in s:
            s = re.sub(rf'"{k}":\s*[^,\n]+', f'"{k}": {val}', s, count=1)
        else:
            s, n = re.subn(r'(\n(\s*)"youtube_id":[^\n]*\n)', rf'\1\2"{k}": {val},\n', s, count=1)
            if not n:
                s = s.replace("{", f'{{\n  "{k}": {val},', 1)
    json.loads(s)
    open(path, "w", encoding="utf-8").write(s)


# ------------------------------------------------ pin пост: бүх хичээлийн жагсаалт
def lesson_rows():
    """[(хичээл, гарчиг, линк)] анги, хичээл, дугаарын дарааллаар. FB пост байвал түүнийг, үгүй бол сайтыг."""
    import glob
    import make_lesson as M
    rows = []
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        c = M.load_cfg(p)
        if c.get("type") == "math":
            label = c["topic"]
        else:
            nl = c.get("new_letters", "")
            label = "Й (хагас и) үсэг" if nl == "й" else f"{nl.upper()} үсэг"
        lid = M.lesson_id(p)
        link = (f"https://www.facebook.com/reel/{c['facebook_id']}" if c.get("facebook_id")
                else f"{SITE}#/{lid}")
        rows.append(((c.get("grade", 1), c.get("subject") != "mongol", c.get("lesson_number") or 0),
                     c.get("grade", 1), c.get("subject", ""), c.get("lesson_number"), label, link))
    return [r[1:] for r in sorted(rows)]


def pin_text():
    icons = {"mongol": "📖", "math": "🔢"}
    lines = ["📌 БҮХ ХИЧЭЭЛ ЭНД БАЙНА", "",
             "1-р ангийн үнэгүй видео хичээлүүд. Хичээлийнхээ линк дээр дараад үзээрэй. "
             "Шинэ хичээл гарах бүрд энэ жагсаалт шинэчлэгдэнэ.", ""]
    cur = None
    for grade, subj, num, label, link in lesson_rows():
        if (grade, subj) != cur:
            if cur:
                lines.append("")
            cur = (grade, subj)
            lines.append(f"{icons.get(subj, '📒')} {grade}-р анги, {SUBJ.get(subj, (subj,))[0]}")
        lines.append(f"{num}. {label}: {link}")
    lines += ["", f"🎮 Дасгал, тоглоом: {SITE}",
              "▶ YouTube: https://www.youtube.com/channel/UCbmSrQ0QNw1n1NB7T5AAxZg",
              "", "#сурагч #1ранги #хүүхдэд"]
    return "\n".join(lines)


def update_pin():
    """Pin постыг шинэчилнэ (байхгүй бол үүсгээд pin хийнэ). Постын id-г буцаана."""
    t = load_token()
    if not t:
        raise FBError("Facebook токен алга (.fb_token)")
    msg = pin_text()
    pid = None
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE, encoding="utf-8") as f:
            pid = json.load(f).get("post_id")
    if pid:
        try:
            _check(requests.post(f"{API}/{pid}", data={"message": msg, "access_token": t["token"]}, timeout=60))
            return pid
        except FBError as e:   # пост устгагдсан бол шинээр үүсгэнэ
            print(f"  Хуучин pin постыг засаж чадсангүй ({e}), шинээр үүсгэнэ.")
    try:
        pid = _check(requests.post(f"{API}/{t['page_id']}/feed",
                                   data={"message": msg, "access_token": t["token"]}, timeout=60))["id"]
    except requests.RequestException as e:
        raise FBError(f"Сүлжээний алдаа: {type(e).__name__}") from None
    with open(PIN_FILE, "w", encoding="utf-8") as f:
        json.dump({"post_id": pid}, f)
    try:   # API pin хийх эрх ихэвчлэн өгдөггүй: тэгвэл хуудсан дээрээ гараар нэг удаа pin хийнэ
        _check(requests.post(f"{API}/{pid}", data={"is_pinned": "true", "access_token": t["token"]}, timeout=60))
    except (FBError, requests.RequestException):
        print("  Постыг хуудсан дээрээ гараар pin хийнэ үү (⋯ > Pin post). Цаашид энэ пост өөрөө шинэчлэгдэнэ.")
    return pid


def pin():
    pid = update_pin()
    print(f"Pin пост бэлэн: https://www.facebook.com/{pid}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        {"setup": setup, "check": check, "queue": queue, "pin": pin}.get(cmd, lambda: sys.exit(__doc__))()
    except FBError as e:
        sys.exit(f"Facebook алдаа: {e}")
