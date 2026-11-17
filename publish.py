#!/usr/bin/env python
"""Хичээлийг YouTube-д автоматаар нийтэлнэ.

Хэрэглээ:
    python publish.py lessons/hicheel_09.json          # бүх алхам
    python publish.py lessons/hicheel_09.json --no-push # git push хийхгүй
    python publish.py --sync                           # зөвхөн playlist-ийн дарааллыг засна
    python publish.py --pending                        # YouTube-д ороогүй бүх хичээлийг дарааллаар нь

Алхмууд:
  1. Бичлэг, YouTube мэдээлэл (гарчиг, тайлбар, thumbnail) байхгүй бол make_lesson.py-аар үүсгэнэ
  2. YouTube руу оруулна ("Made for kids", Боловсрол ангилал)
  3. Thumbnail тавина
  4. youtube_id-г хичээлийн JSON-д бичнэ
  5. Анги + хичээлийн playlist-д дугаарын дарааллаар нэмнэ (байхгүй бол үүсгэнэ)
  6. build_site.py ажиллуулаад git commit + push хийнэ

Нэг удаагийн тохиргоо: Google Cloud-оос татсан OAuth client файлыг client_secret.json нэрээр
энэ хавтаст хадгална. Анх ажиллуулахад хөтөч нээгдэж YouTube сувгаа сонгоод зөвшөөрнө.
Нэвтрэлтийн токен .youtube_token.json-д хадгалагдана (git-д орохгүй).
"""
import glob
import json
import os
import re
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)  # Python 3.10 дэмжлэгийн анхааруулга
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_lesson as M  # noqa: E402

CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
TOKEN = os.path.join(ROOT, ".youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube"]
SUBJECTS = {
    "mongol": "Монгол хэл", "math": "Математик", "orchin": "Хүн ба орчин", "baigal": "Хүн ба байгаль",
    "niigem": "Хүн ба нийгэм", "english": "Англи хэл", "art": "Дүрслэх урлаг, технологи",
    "music": "Хөгжим", "pe": "Биеийн тамир",
}
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


# ------------------------------------------------ нэвтрэлт
def youtube():
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(TOKEN):
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            creds = None
    if not creds or not creds.valid:
        if not os.path.exists(CLIENT_SECRET):
            sys.exit("client_secret.json олдсонгүй. README-ийн 'YouTube автомат нийтлэл' хэсгийг харна уу.")
        print("Хөтөч нээгдэнэ: YouTube сувгаа сонгоод 'Allow' дарна уу.")
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


# ------------------------------------------------ туслах
def run(*cmd):
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT, env=ENV)


def parse_meta(path):
    """make_lesson.py --youtube-ийн бичсэн txt файлаас гарчиг, тайлбар, шошгыг уншина."""
    text = open(path, encoding="utf-8").read()
    heads = {"ГАРЧИГ (Title):": "title", "ТАЙЛБАР (Description):": "desc", "ШОШГО (Tags):": "tags", "ТОХИРГОО:": None}
    out, key, buf = {}, None, []
    for line in text.splitlines():
        if line in heads:
            if key:
                out[key] = "\n".join(buf).strip()
            key, buf = heads[line], []
        else:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    tags, total = [], 0
    for t in (s.strip() for s in out["tags"].split(",")):
        if t and total + len(t) + 2 <= 480:   # YouTube: нийт 500 тэмдэгт
            tags.append(t)
            total += len(t) + 2
    return out["title"][:100], out["desc"], tags


def playlist_title(cfg):
    if cfg.get("playlist"):
        return cfg["playlist"]
    subj = SUBJECTS.get(cfg.get("subject", "mongol"), cfg.get("subject", ""))
    return f"{cfg.get('grade', 1)}-р анги {subj.lower()}"   # жишээ: "1-р анги монгол хэл"


def norm(title):
    return re.sub(r"[^\w]+", " ", title.lower()).strip()


def set_youtube_id(path, vid):
    s = open(path, encoding="utf-8").read()
    if '"youtube_id"' in s:
        s = re.sub(r'"youtube_id":\s*"[^"]*"', f'"youtube_id": "{vid}"', s, count=1)
    else:
        s, n = re.subn(r'(\n(\s*)"lesson_number":[^\n]*\n)', rf'\1\2"youtube_id": "{vid}",\n', s, count=1)
        if not n:
            s = s.replace("{", f'{{\n  "youtube_id": "{vid}",', 1)
    json.loads(s)  # эвдэрсэн эсэхийг шалгана
    open(path, "w", encoding="utf-8").write(s)


def with_retry(fn, what):
    from googleapiclient.errors import HttpError
    for i in range(5):
        try:
            return fn()
        except HttpError as e:
            if e.resp.status < 500 or i == 4:
                raise
            print(f"  {what}: түр алдаа ({e.resp.status}), дахин оролдоно...")
            time.sleep(2 ** i)


# ------------------------------------------------ YouTube алхмууд
def upload(yt, mp4, title, desc, tags, privacy):
    from googleapiclient.http import MediaFileUpload
    body = {
        "snippet": {"title": title, "description": desc, "tags": tags, "categoryId": "27",
                    "defaultLanguage": "mn", "defaultAudioLanguage": "mn"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": True, "embeddable": True},
    }
    media = MediaFileUpload(mp4, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = with_retry(req.next_chunk, "Оруулалт")
        if status:
            print(f"  Оруулж байна: {int(status.progress() * 100)}%", flush=True)
    return resp


def set_thumbnail(yt, vid, png):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from PIL import Image
    jpg = os.path.join(ROOT, ".tts_cache", f"thumb_{vid}.jpg")
    Image.open(png).convert("RGB").save(jpg, quality=90)   # 2MB-аас бага байлгана
    try:
        with_retry(lambda: yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(jpg)).execute(), "Thumbnail")
        print("  Thumbnail тавигдлаа")
    except HttpError as e:
        print(f"  Анхаар: thumbnail тавьж чадсангүй ({e.resp.status}). Studio дээр гараар тавина уу: {png}")
    finally:
        os.remove(jpg)


def find_or_create_playlist(yt, title):
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req:
        resp = req.execute()
        for p in resp.get("items", []):
            if norm(p["snippet"]["title"]) == norm(title):
                return p["id"], False
        req = yt.playlists().list_next(req, resp)
    print(f"  Шинэ playlist үүсгэж байна: {title}")
    body = {"snippet": {"title": title, "description":
                        f"{title}. Хичээлүүд дугаарын дарааллаараа.\n\n" + "\n".join(M.DESC_LINKS),
                        "defaultLanguage": "mn"},
            "status": {"privacyStatus": "public"}}
    return yt.playlists().insert(part="snippet,status", body=body).execute()["id"], True


def playlist_items(yt, pid, new=False):
    from googleapiclient.errors import HttpError
    for attempt in range(6):
        try:
            items, req = [], yt.playlistItems().list(part="snippet", playlistId=pid, maxResults=50)
            while req:
                resp = req.execute()
                items += resp.get("items", [])
                req = yt.playlistItems().list_next(req, resp)
            return items
        except HttpError as e:   # шинэ playlist хэдэн секундийн дараа л харагддаг
            if e.resp.status != 404 or not new or attempt == 5:
                raise
            time.sleep(3)


def sync_playlists(yt):
    """Бүх хичээлийг playlist бүрт дугаарын дарааллаар байрлуулна."""
    groups = {}
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        cfg = M.load_cfg(p)
        if cfg.get("youtube_id"):
            groups.setdefault(playlist_title(cfg), []).append((cfg.get("lesson_number") or 0, cfg["youtube_id"]))
    for title, lessons in groups.items():
        pid, new = find_or_create_playlist(yt, title)
        want = [v for _, v in sorted(lessons)]
        changed = 0
        for pos, vid in enumerate(want):
            items = playlist_items(yt, pid, new)
            cur = next((it for it in items if it["snippet"]["resourceId"]["videoId"] == vid), None)
            if cur is None:
                yt.playlistItems().insert(part="snippet", body={"snippet": {
                    "playlistId": pid, "position": pos,
                    "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
                changed += 1
            elif cur["snippet"]["position"] != pos:
                yt.playlistItems().update(part="snippet", body={"id": cur["id"], "snippet": {
                    "playlistId": pid, "position": pos, "resourceId": cur["snippet"]["resourceId"]}}).execute()
                changed += 1
        print(f"  Playlist «{title}»: {len(want)} хичээл, {changed} өөрчлөлт")
        print(f"  https://www.youtube.com/playlist?list={pid}")


# ------------------------------------------------ үндсэн
def pending_lessons():
    """YouTube-д ороогүй хичээлүүд: анги, хичээл, дугаарын дарааллаар."""
    out = []
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        cfg = M.load_cfg(p)
        if not cfg.get("youtube_id"):
            out.append(((cfg.get("grade", 1), cfg.get("subject", ""), cfg.get("lesson_number") or 0), p))
    return [p for _, p in sorted(out)]


def publish_one(path, yt=None):
    """Нэг хичээлийг нийтэлнэ. YouTube-ийн өдрийн хязгаарт хүрвэл False буцаана."""
    from googleapiclient.errors import HttpError
    cfg = M.load_cfg(path)
    name = M.lesson_id(path)
    rel = os.path.relpath(path, ROOT)
    mp4 = os.path.join(ROOT, "videos", name + ".mp4")
    meta = os.path.join(ROOT, "youtube", name + "_youtube.txt")
    thumb = os.path.join(ROOT, "youtube", name + "_thumbnail.png")
    newest_input = max(os.path.getmtime(path), os.path.getmtime(os.path.join(ROOT, "settings.json")))
    if not os.path.exists(mp4) or os.path.getmtime(mp4) < newest_input:
        run(sys.executable, "make_lesson.py", rel)
    if not os.path.exists(meta) or os.path.getmtime(meta) < newest_input:
        run(sys.executable, "make_lesson.py", rel, "--youtube")
    title, desc, tags = parse_meta(meta)

    yt = yt or youtube()
    privacy = cfg.get("youtube_privacy", "public")
    print(f"YouTube руу оруулж байна: {title}")
    try:
        resp = upload(yt, mp4, title, desc, tags, privacy)
    except HttpError as e:
        if "uploadLimitExceeded" in str(e) or "quotaExceeded" in str(e):
            print("  YouTube-ийн өдрийн хязгаарт хүрлээ. Маргааш дахин ажиллуулна уу: python publish.py --pending")
            return False
        raise
    vid = resp["id"]
    set_youtube_id(path, vid)   # дараагийн алхам алдаа гарсан ч давхар оруулахгүй
    print(f"  Оруулсан: https://youtu.be/{vid} ({resp['status'].get('privacyStatus')})")
    set_thumbnail(yt, vid, thumb)
    sync_playlists(yt)
    facebook_post(path)

    run(sys.executable, "build_site.py")
    if "--no-push" not in sys.argv:
        run("git", "add", "lessons", "site", "youtube")
        run("git", "commit", "-q", "-m", f"{cfg.get('lesson_number', '')}-р хичээл YouTube-д нийтлэв ({vid})")
        run("git", "push", "-q")
        print("Сайт хэдэн минутын дараа шинэчлэгдэнэ: https://suragch.cloud/")
    if resp["status"].get("privacyStatus") != privacy:
        print(f"  Анхаар: бичлэг {resp['status'].get('privacyStatus')} болсон. Studio дээр шалгана уу: "
              f"https://studio.youtube.com/video/{vid}/edit")
    return True


def facebook_post(path):
    """Facebook хуудсанд хуваарьтай пост. Токен байхгүй эсвэл алдаа гарвал анхааруулаад үргэлжилнэ."""
    import fb
    if not fb.load_token():
        return False
    cfg = M.load_cfg(path)
    if cfg.get("facebook_id"):
        return False
    name = M.lesson_id(path)
    mp4 = os.path.join(ROOT, "videos", name + ".mp4")
    thumb = os.path.join(ROOT, "youtube", name + "_thumbnail.png")
    try:
        print("  Facebook руу оруулж байна...", flush=True)
        _, when = fb.post_lesson(path, mp4, thumb)
        print(f"  Facebook: {when.strftime('%m-%d %H:%M')}-д нийтлэгдэнэ")
        return True
    except fb.FBError as e:
        print(f"  Анхаар: Facebook-д оруулж чадсангүй: {e}")
        return False


def facebook_backlog():
    """YouTube-д орсон ч Facebook-д ороогүй хичээлүүд: эхлээд математик, дараа нь бусад, дугаарын дарааллаар."""
    out = []
    for p in glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True):
        cfg = M.load_cfg(p)
        if cfg.get("youtube_id") and not cfg.get("facebook_id"):
            out.append(((cfg.get("subject") != "math", cfg.get("grade", 1), cfg.get("lesson_number") or 0), p))
    return [p for _, p in sorted(out)]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--facebook" in sys.argv:
        todo = facebook_backlog()
        print(f"Facebook-д ороогүй {len(todo)} хичээл байна (өдөрт 1, орой 20:00).")
        done = 0
        for p in todo:
            print(f"\n== {os.path.relpath(p, ROOT)}")
            if not facebook_post(p):
                break
            done += 1
        if done and "--no-push" not in sys.argv:
            run("git", "add", "lessons")
            run("git", "commit", "-q", "-m", f"Facebook: {done} хичээлийн пост хуваарьт орлоо")
            run("git", "push", "-q")
        return
    if "--sync" in sys.argv:
        return sync_playlists(youtube())
    if "--pending" in sys.argv:
        todo = pending_lessons()
        print(f"YouTube-д ороогүй {len(todo)} хичээл байна.")
        yt = youtube() if todo else None
        for i, p in enumerate(todo):
            print(f"\n== {os.path.relpath(p, ROOT)}")
            if not publish_one(p, yt):
                print(f"Үлдсэн: {len(todo) - i} хичээл.")
                return
        print("\nБүгд нийтлэгдлээ.")
        return
    if len(args) != 1:
        sys.exit(__doc__)
    path = os.path.abspath(args[0])
    cfg = M.load_cfg(path)
    if cfg.get("youtube_id") and "--force" not in sys.argv:
        sys.exit(f"Энэ хичээл аль хэдийн YouTube-д байна: https://youtu.be/{cfg['youtube_id']}\n"
                 "Дахин оруулах бол --force, зөвхөн playlist засах бол --sync.")
    publish_one(path)


if __name__ == "__main__":
    main()
