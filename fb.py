#!/usr/bin/env python
"""Facebook хуудас руу хичээлийн бичлэгийг нийтэлнэ (Graph API).

Хэрэглээ:
    python fb.py setup     # .fb_setup.json-оос хугацаагүй Page token гаргаж .fb_token-д хадгална
    python fb.py check     # токен ажиллаж байгаа эсэх, хуудасны нэр
    python fb.py queue     # хуваарьт орсон постууд

Бичлэг бүр шууд гарахгүй: өдөрт 1 пост, орой 20:00 цагт (Улаанбаатар) хуваарьтай нийтлэгдэнэ.
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
SITE = "https://suragch.cloud/"


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
        letters = ", ".join(cfg["letters"])
        head = f"{cfg.get('title', '')} {num}-р хичээл: {letters} үсэг"
        what = f"Шинэ үсэг: {cfg.get('new_letters', '').upper()}. Үсгээ давтаж, үе холбож, үг, өгүүлбэр уншина."
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
    """Бичлэгийг хуудсанд хуваарьтай нийтэлнэ. (video_id, unix цаг) буцаана."""
    import make_lesson as M
    t = load_token()
    if not t:
        raise FBError("Facebook токен алга (.fb_token)")
    cfg = M.load_cfg(path)
    lid = M.lesson_id(path)
    desc, title = post_text(cfg, lid, cfg.get("youtube_id", ""))
    when = when or next_slot()
    jpg = os.path.join(ROOT, ".tts_cache", f"fbthumb_{lid}.jpg")
    from PIL import Image
    Image.open(thumb_png).convert("RGB").save(jpg, quality=90)
    data = {"title": title, "description": desc, "access_token": t["token"],
            "published": "false", "scheduled_publish_time": str(int(when.timestamp()))}
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        {"setup": setup, "check": check, "queue": queue}.get(cmd, lambda: sys.exit(__doc__))()
    except FBError as e:
        sys.exit(f"Facebook алдаа: {e}")
