#!/usr/bin/env python
"""lessons/*.json файлуудаас вэб сайтын өгөгдөл, дууг бэлдэнэ.

Хэрэглээ:
    python build_site.py

Үр дүн: site/data/lessons.js, site/audio/*.mp3, site/videos/*.mp4
YouTube-д байршуулсны дараа JSON файлд "youtube_id" нэмбэл сайт YouTube-ээс тоглуулна.
"""
import glob
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_lesson as M  # noqa: E402

SITE = os.path.join(ROOT, "site")


def build_lesson(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    M.validate(cfg)
    name = M.lesson_id(path)
    tts = M.TTS(cfg.get("voice", "mn-MN-YesuiNeural"), os.path.join(ROOT, ".tts_cache"))
    lesson = M.Lesson(cfg, tts)
    rn, rr = lesson.rn, lesson.rr

    def audio(text, rate):
        tts.pending.add((text, rate))
        return "audio/" + os.path.basename(tts.path(text, rate))

    def R(text):  # уншлагын хурдаар
        return audio(text, rr)

    def N(text):  # тайлбарын хурдаар
        return audio(text, rn)

    letters = cfg["letters"]
    info = cfg.get("letter_info", {})
    data = {
        "id": name,
        "subject": cfg.get("subject", "mongol"),
        "type": cfg.get("type", "reading"),
        "grade": cfg.get("grade", 1),
        "number": cfg.get("lesson_number"),
        "title": cfg.get("title", "Уншиж сурцгаая!"),
        "letters": letters,
        "new": cfg.get("new_letters", ""),
        "youtube_id": cfg.get("youtube_id", ""),
        "video": "",
        "letter_cards": [],
        "syllables": [[{"t": s, "a": R(M.cap(s) + ".")} for s in g] for g in lesson.syllable_groups()],
        "words": [],
        "sentences": [],
    }
    for ch in letters:
        i = info.get(ch, {})
        card = {"ch": ch, "a": N(i.get("say", f"{ch.upper()} үсэг."))}
        if i.get("example"):
            card.update(example=i["example"], emoji=i.get("emoji", ""), ea=R(M.cap(i["example"]) + "."))
        data["letter_cards"].append(card)
    for w in cfg["words"]:
        syl = w.get("syl") or [w["w"]]
        item = {"w": w["w"], "a": R(M.cap(w["w"]) + "."), "emoji": w.get("emoji", ""),
                "syl": [{"t": s, "a": R(M.cap(s) + ".")} if len(syl) > 1 else {"t": s} for s in syl]}
        if w.get("explain"):
            item.update(explain=w["explain"], xa=N(w["explain"]))
        data["words"].append(item)
    for s in cfg.get("sentences", []):
        toks = s["s"].split(" ")
        data["sentences"].append({
            "s": s["s"], "a": R(s["s"]), "emoji": s.get("emoji", ""),
            "words": [{"t": tk, "a": R(M.cap(tk.strip(",.!?")) + ".")} for tk in toks],
        })
    # тоглоомд ашиглах үгс (давхардалгүй)
    pool = {w["w"]: w for w in data["words"]}
    for q in cfg.get("quiz", []):
        if q not in pool:
            pool[q] = {"w": q, "a": R(M.cap(q) + "."), "emoji": ""}
    data["game"] = [{"w": w["w"], "a": w["a"], "emoji": w.get("emoji", "")} for w in pool.values()]

    tts.generate_all()
    os.makedirs(os.path.join(SITE, "audio"), exist_ok=True)
    for text, rate in tts.pending:
        src = tts.path(text, rate)
        dst = os.path.join(SITE, "audio", os.path.basename(src))
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    vid = os.path.join(ROOT, "videos", name + ".mp4")
    if os.path.exists(vid):
        os.makedirs(os.path.join(SITE, "videos"), exist_ok=True)
        shutil.copy2(vid, os.path.join(SITE, "videos", name + ".mp4"))
        data["video"] = f"videos/{name}.mp4"
    thumb = os.path.join(ROOT, "youtube", name + "_thumbnail.png")
    if os.path.exists(thumb):
        os.makedirs(os.path.join(SITE, "img"), exist_ok=True)
        shutil.copy2(thumb, os.path.join(SITE, "img", name + ".png"))
        data["poster"] = f"img/{name}.png"
    return data


def main():
    lessons = [build_lesson(p) for p in sorted(glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True))]
    lessons.sort(key=lambda d: (d["grade"], d["subject"], d["number"] or 0))
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    with open(os.path.join(SITE, "data", "lessons.js"), "w", encoding="utf-8") as f:
        f.write("// build_site.py-аар үүсгэсэн. Гараар засах шаардлагагүй.\n")
        f.write("window.LESSONS = ")
        json.dump(lessons, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    print(f"Бэлэн: {len(lessons)} хичээл -> site/")


if __name__ == "__main__":
    main()
