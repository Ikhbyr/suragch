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
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import make_lesson as M  # noqa: E402

SITE = os.path.join(ROOT, "site")


def math_data(cfg, R, N):
    """Математикийн хичээл: тооны карт, бодлого, тоглоомын тохиргоо."""
    from make_math import NOM, ATTR, ORD, ORDT, expr_sentence, cmp_sign
    nums, problems, maxn, kinds = [], [], 0, set()
    for sec in cfg["sections"]:
        for it in sec["items"]:
            ty = it["type"]
            if ty in ("ordinal", "which", "find", "sides"):   # дэс дугаар
                kinds.add("ordinal")
                row = it["row"]
                maxn = max(maxn, len(row))
                if ty == "ordinal" and not nums:
                    nums += [{"n": i + 1, "ord": True, "word": ORD[i + 1], "emoji": row[i], "row": row}
                             for i in range(len(row))]
                elif ty == "which":
                    n = it["target"] + 1
                    names = it.get("names")
                    ans = it.get("answer") or (f"{M.cap(names[n - 1])} {ORDT[n]} байна." if names else M.cap(ORD[n]) + ".")
                    problems.append({"row": row, "ring": n - 1, "t": [f"{n}-р"], "h": 0, "a": N(ans)})
                elif ty == "find":
                    n, k = it["n"], len(row)
                    i = k - n if it.get("from") == "right" else n - 1
                    problems.append({"row": row, "ring": i, "t": [f"{n}-р"], "h": 0, "right": it.get("from") == "right",
                                     "a": N(it.get("answer") or f"Энэ бол {ORD[n]}.")})
                elif ty == "sides":
                    i, k, names = it["target"], len(row), it["names"]
                    problems.append({"row": row, "ring": i, "t": ["зүүн", f"{i + 1}-р"], "h": 1,
                                     "a": N(f"{M.cap(names[i])} зүүн талаас {ORDT[i + 1]} байна.")})
                    problems.append({"row": row, "ring": i, "t": ["баруун", f"{k - i}-р"], "h": 1, "right": True,
                                     "a": N(f"{M.cap(names[i])} баруун талаас {ORDT[k - i]} байна.")})
                continue
            kinds.add(ty if ty != "expr" else ("compare" if it["op"] in "<>=" else "sub" if it["op"] != "+" else "add"))
            for k in ("n", "a", "b", "to", "from"):
                if isinstance(it.get(k), int):
                    maxn = max(maxn, it[k])
            e = it.get("emoji", "")
            if ty == "number":
                say = it.get("say") or (f"{M.cap(ATTR[it['n']])} {it['obj']}." if it.get("obj") else "")
                nums.append({"n": it["n"], "word": NOM[it["n"]], "emoji": e, "sa": N(say) if say else ""})
            elif ty in ("add", "sub") or (ty == "expr" and it["op"] in "+−-"):
                op = "+" if ty == "add" or it.get("op") == "+" else "−"
                a, b = it["a"], it["b"]
                c = a + b if op == "+" else a - b
                problems.append({"t": [str(a), op, str(b), "=", str(c)], "h": 4, "emoji": e,
                                 "a": N(expr_sentence(a, op, b, c))})
            elif ty == "compare" or (ty == "expr" and it["op"] in "<>="):
                a, b = it["a"], it["b"]
                problems.append({"t": [str(a), cmp_sign(a, b), str(b)], "h": 1, "emoji": e,
                                 "a": N(expr_sentence(a, "<", b))})
            elif ty == "split":
                n, a, b = it["n"], it["a"], it["b"]
                problems.append({"t": [str(n), "→", str(a), "ба", str(b)], "h": 4, "emoji": e,
                                 "a": N(it.get("say") or f"{M.cap(NOM[n])} бол {NOM[a]} ба {NOM[b]}.")})
    if "ordinal" in kinds:
        game = "ordinal"
    elif {"add", "sub"} <= kinds or ("compare" in kinds and ({"add", "sub"} & kinds)):
        game = "mix"
    elif "add" in kinds:
        game = "add"
    elif "sub" in kinds:
        game = "sub"
    elif "compare" in kinds:
        game = "compare"
    elif "split" in kinds:
        game = "split"
    else:
        game = "count"
    return {
        "chips": [str(c) for c in cfg["chips"]], "new_chips": [str(c) for c in cfg.get("new_chips", [])],
        "topic": cfg["topic"], "nums": nums, "problems": problems,
        "game": {"kind": game, "max": max(3, min(10, maxn))},
        "num_audio": [R(M.cap(w) + ".") for w in NOM],
        **({"ord_audio": [R(M.cap(w) + ".") if w else "" for w in ORD], "ord_q_audio": N("Хэд дэх вэ?")}
           if "ordinal" in kinds else {}),
        "q_audio": N("Хэд байна?"),
        "cmp_audio": {"<": N("Бага."), ">": N("Их."), "=": N("Тэнцүү.")},
    }


def build_lesson(path):
    cfg = M.load_cfg(path)
    M.validate(cfg)
    name = M.lesson_id(path)
    tts = M.TTS(cfg, os.path.join(ROOT, ".tts_cache"))
    lesson = M.lesson_class(cfg)(cfg, tts)
    rn, rr = lesson.rn, lesson.rr

    def audio(text, rate):
        tts.pending.add((text, rate))
        return "audio/" + os.path.splitext(os.path.basename(tts.path(text, rate)))[0] + ".mp3"

    def R(text):  # уншлагын хурдаар
        return audio(text, rr)

    def N(text):  # тайлбарын хурдаар
        return audio(text, rn)

    if cfg.get("type") == "math":
        data = {"id": name, "subject": cfg.get("subject", "math"), "type": "math", "grade": cfg.get("grade", 1),
                "number": cfg.get("lesson_number"), "title": cfg.get("title", ""),
                "youtube_id": cfg.get("youtube_id", ""), "video": "", "glyph": cfg.get("glyph", ""),
                **math_data(cfg, R, N)}
        return finish(data, tts, name)

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
        "topic": cfg.get("topic", "") if not cfg.get("new_letters") else "",
        "glyph": cfg.get("glyph", ""),
        "letter_cards": [],
        "syllables": [[{"t": s, "a": R(M.cap(s) + ".")} for s in g] for g in lesson.syllable_groups()],
        "words": [],
        "sentences": [],
        "listen": [],
    }
    for ch in letters:
        i = info.get(ch, {})
        card = {"ch": ch, "a": N(i.get("say", f"{ch.upper()} үсэг."))}
        if i.get("example"):
            card.update(example=i["example"], emoji=i.get("emoji", ""), ea=R(M.cap(i["example"]) + "."),
                        listen=bool(i.get("listen")))
        data["letter_cards"].append(card)
    new = cfg.get("new_letters", "")
    for w in cfg.get("listen_words", []):   # сонсоод олох үгс: шинэ үсгийг тодруулна
        data["listen"].append({"w": w["w"], "a": R(M.cap(w["w"]) + "."), "emoji": w.get("emoji", ""),
                               "hl": [i for i, c in enumerate(w["w"]) if c.lower() in new]})
    for w in cfg.get("words", []):
        syl = w.get("syl") or [w["w"]]
        item = {"w": w["w"], "a": R(M.cap(w["w"]) + "."), "emoji": w.get("emoji", ""),
                "syl": [{"t": s, "a": R(M.cap(s) + ".")} if len(syl) > 1 else {"t": s} for s in syl]}
        if w.get("explain"):
            item.update(explain=w["explain"], xa=N(w["explain"]))
        data["words"].append(item)
    story = cfg.get("story")
    if story:
        data["story_title"] = story["title"]
        data["story_emoji"] = story.get("emoji", "")
    for s, is_story in [(x, False) for x in cfg.get("sentences", [])] + [(x, True) for x in (story or {}).get("sentences", [])]:
        toks = s["s"].split(" ")
        data["sentences"].append({
            "s": s["s"], "a": R(s["s"]), "emoji": s.get("emoji", ""), "story": is_story,
            "words": [{"t": tk, "a": R(M.cap(tk.strip(",.!?")) + ".")} for tk in toks],
        })
    # тоглоомд ашиглах үгс (давхардалгүй)
    pool = {w["w"]: w for w in data["words"]}
    for q in cfg.get("quiz", []):
        if q not in pool:
            pool[q] = {"w": q, "a": R(M.cap(q) + "."), "emoji": ""}
    data["game"] = [{"w": w["w"], "a": w["a"], "emoji": w.get("emoji", "")} for w in pool.values()]
    return finish(data, tts, name)


def finish(data, tts, name):
    """Дууг бэлтгэж сайт руу хуулна, видео/зургийг холбоно."""
    tts.generate_all()
    os.makedirs(os.path.join(SITE, "audio"), exist_ok=True)
    used = set()
    for text, rate in tts.pending:
        src = tts.path(text, rate)
        dst = os.path.join(SITE, "audio", os.path.splitext(os.path.basename(src))[0] + ".mp3")
        if not os.path.exists(dst) and tts.dry:
            continue   # туршилт: дуу үүсгээгүй
        if not os.path.exists(dst):
            if src.endswith(".mp3"):
                shutil.copy2(src, dst)
            else:  # Chimege WAV -> вэбэд хөнгөн MP3
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-b:a", "64k", dst], check=True)
        used.add(os.path.basename(dst))
    vid = os.path.join(ROOT, "videos", name + ".mp4")
    site_vid = os.path.join(SITE, "videos", name + ".mp4")
    if data["youtube_id"]:  # YouTube-ээс тоглуулна, сайтад MP4 хадгалах шаардлагагүй
        if os.path.exists(site_vid):
            os.remove(site_vid)
    elif os.path.exists(vid):
        os.makedirs(os.path.join(SITE, "videos"), exist_ok=True)
        shutil.copy2(vid, site_vid)
        data["video"] = f"videos/{name}.mp4"
    thumb = os.path.join(ROOT, "youtube", name + "_thumbnail.png")
    if os.path.exists(thumb):
        os.makedirs(os.path.join(SITE, "img"), exist_ok=True)
        shutil.copy2(thumb, os.path.join(SITE, "img", name + ".png"))
        data["poster"] = f"img/{name}.png"
    data["_audio"] = sorted(used)
    return data


def added_time(path):
    """Хичээл анх git-д орсон хугацаа (эсвэл файлын огноо)."""
    r = subprocess.run(["git", "log", "--diff-filter=A", "--format=%ct", "--", path],
                       capture_output=True, text=True, cwd=ROOT)
    out = r.stdout.split()
    return int(out[-1]) if out else int(os.path.getmtime(path))


def main():
    paths = sorted(glob.glob(os.path.join(ROOT, "lessons", "**", "*.json"), recursive=True))
    lessons = [build_lesson(p) for p in paths]
    for d, p in zip(lessons, paths):   # "Шинэ хичээлүүд" жагсаалтад: нэмэгдсэн дараалал
        d["added"] = added_time(p)
    used = set()
    for d in lessons:
        used.update(d.pop("_audio"))
    adir = os.path.join(SITE, "audio")
    stale = [f for f in os.listdir(adir) if f not in used]
    for f in ([] if os.environ.get("TTS_DRY") == "1" else stale):   # хэрэглэгдэхээ больсон хуучин дуу
        os.remove(os.path.join(adir, f))
    lessons.sort(key=lambda d: (d["grade"], d["subject"], d["number"] or 0))
    os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
    with open(os.path.join(SITE, "data", "lessons.js"), "w", encoding="utf-8") as f:
        f.write("// build_site.py-аар үүсгэсэн. Гараар засах шаардлагагүй.\n")
        f.write("window.LESSONS = ")
        json.dump(lessons, f, ensure_ascii=False, indent=1)
        f.write(";\n")
    stamp_assets()
    print(f"Бэлэн: {len(lessons)} хичээл -> site/")


def stamp_assets():
    """index.html дахь css/js холбоосонд агуулгын хэш (?v=...) нэмнэ: хөтөч хуучин хуулбар ашиглахгүй."""
    import hashlib
    import re
    page = os.path.join(SITE, "index.html")
    html = open(page, encoding="utf-8").read()

    def repl(m):
        path = os.path.join(SITE, m.group(2))
        h = hashlib.sha1(open(path, "rb").read()).hexdigest()[:10]
        return f'{m.group(1)}="{m.group(2)}?v={h}"'
    new = re.sub(r'(href|src)="((?:style\.css|app\.js|data/lessons\.js|data/support\.js))(?:\?v=[0-9a-f]+)?"', repl, html)
    if new != html:
        open(page, "w", encoding="utf-8").write(new)


if __name__ == "__main__":
    main()
