# Сурагч — бага ангийн хичээл

Бага ангийн (1–5-р анги) бүх хичээлийг хамрах зорилготой. «Уншиж сурцгаая!» нь 1-р ангийн Монгол хэлний (уншлагын) цуврал.

Хичээлүүдийг `lessons/<анги>/<хичээл>/` хавтсанд хадгалж болно (жишээ нь `lessons/1/math/hicheel_01.json`). Хичээлийн түлхүүрүүд (`subject`): `mongol`, `math`, `orchin`, `baigal`, `niigem`, `english`, `art`, `music`, `pe`. Шинэ хичээл нэмэх бол `site/app.js` доторх `SUBJECTS` жагсаалтад нэмнэ.

Сайт: https://suragch.cloud/

Сайтыг шинэчлэх: `python build_site.py` ажиллуулаад `git add -A`, `git commit -m "..."`, `git push`. Хэдхэн минутын дараа сайт автоматаар шинэчлэгдэнэ.

## Хавтаснууд

| Хавтас / файл | Юу байдаг вэ |
|---|---|
| `lessons/hicheel_07.json` | Хичээлийн агуулга: үсэг, үг, өгүүлбэр, тоглоом |
| `make_lesson.py` | Видео, YouTube-д оруулах мэдээлэл үүсгэнэ |
| `build_site.py` | Вэб сайтын өгөгдөл, дууг бэлдэнэ |
| `make_channel_art.py` | YouTube сувгийн баннер, профайл, watermark зураг |
| `videos/` | Бэлэн видеонууд |
| `youtube/` | YouTube-д оруулах гарчиг, тайлбар, нүүр зураг |
| `site/` | Вэб сайт. Энэ хавтсыг бүхэлд нь интернэтэд байршуулна |

## Шинэ хичээл нэмэх

1. `lessons/hicheel_07.json` файлыг `hicheel_08.json` нэрээр хуулна.
2. `grade` (анги: 1–5), `subject` (дээрх түлхүүрүүдээс) болон `letters`, `new_letters`, `letter_info`, `words`, `sentences`, `quiz` хэсгийг шинэчилнэ.
   Уншуулах үгэнд үзээгүй үсэг орвол скрипт анхааруулна.
3. Дараах командуудыг ажиллуулна:

```
python make_lesson.py lessons/hicheel_08.json            # видео
python make_lesson.py lessons/hicheel_08.json --youtube  # YouTube-ийн мэдээлэл + нүүр зураг
python build_site.py                                     # сайтыг шинэчилнэ
```

## YouTube-д байршуулах

1. https://studio.youtube.com → **Create → Upload videos** → `videos/hicheel_07.mp4`
2. Гарчиг, тайлбар, шошгыг `youtube/hicheel_07_youtube.txt` файлаас хуулна.
3. Thumbnail: `youtube/hicheel_07_thumbnail.png` (thumbnail оруулахын тулд сувгаа утсаар баталгаажуулсан байх шаардлагатай).
4. Audience: **Yes, it's made for kids** гэж сонгоно.
5. Visibility: **Public**.
6. Видеоны линкээс ID-г нь авна: `https://youtu.be/AbC123xyz` гэвэл ID нь `AbC123xyz`.
   JSON файлд `"youtube_id": "AbC123xyz",` гэж нэмээд `python build_site.py`-г ажиллуулна.
   Ингэснээр сайт видеог YouTube-ээс тоглуулна.

## Сайтыг интернэтэд гаргах

**Хамгийн хялбар нь Netlify Drop:** https://app.netlify.com/drop хуудас руу `site` хавтсыг чирж оруулна.
Хэдэн секундийн дотор `https://....netlify.app` гэсэн хаягтай сайт бэлэн болно. Бүртгэл үүсгэвэл хаягаа өөрчилж, өөрийн домэйн холбож болно.

**GitHub Pages:** шинэ repository үүсгээд `site` хавтсын доторх файлуудыг оруулна. Дараа нь
Settings → Pages → Branch: `main` / root гэж тохируулна.

Компьютер дээрээ шалгахдаа `site/index.html`-ийг хөтчөөр нээхэд болно.
