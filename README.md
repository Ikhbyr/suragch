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

## Дуу хоолой, арын хөгжим

- Нийтлэг тохиргоо `settings.json` файлд байна: `tts_provider` (`chimege` эсвэл `edge`), Chimege-ийн хоолой (`voice`), өнгө (`pitch`), хурд, арын хөгжмийн чанга (`music_volume`, 0 бол хөгжимгүй).
- Chimege токенийг `.chimege_token` файлд хадгална (git-д орохгүй). Терминалд:
  `Set-Content -Path .chimege_token -Value (Read-Host "Chimege token") -Encoding ascii`
- Бүх хоолойн жишээ сонсох: `python make_lesson.py --voices` → `samples/` хавтас.
- Нэг дуудалт = 200 тэмдэгт хүртэл, 8₮. Үүсгэсэн дуу `.tts_cache`-д хадгалагдах тул дахин төлөхгүй.

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

Эсвэл нэг командаар бүгдийг нь хийнэ (доорх «YouTube автомат нийтлэл»).

## Математикийн хичээл

`lessons/1/math/hicheel_NN.json` (`"type": "math"`). Хэсгүүд нь `sections[].items[]`-ээс бүрдэнэ:
`number`, `count`, `howmany`, `sequence`, `missing`, `sign`, `compare`, `split`, `add`, `sub`, `expr`.
Төрөл бүрийн тайлбар `make_math.py`-ийн эхэнд бий. Видео, сайт, YouTube нийтлэл уншлагын хичээлтэй адилхан:

```
python publish.py lessons/1/math/hicheel_01.json
```

Дуугүй урьдчилсан зураг (Chimege дуудахгүй): `TTS_DRY=1 python make_lesson.py lessons/1/math/hicheel_01.json --snap`

Эцэг эхийн группт тавих зарын загвар: `zar/ezeg_ehchuudad.md`

## YouTube автомат нийтлэл

```
python publish.py lessons/hicheel_09.json   # видео үүсгэх → YouTube → thumbnail → playlist → сайт → push
python publish.py --sync                    # зөвхөн playlist-ийн дарааллыг засна
python publish.py --pending                 # YouTube-д ороогүй бүх хичээлийг дарааллаар нь
```

- Шинэ суваг өдөрт цөөн бичлэг оруулах хязгаартай (`uploadLimitExceeded`). Хязгаарт хүрвэл скрипт
  зогсоно. Маргааш нь `--pending`-ээр үлдсэнийг нь оруулна.
- YouTube-д ороогүй хичээлийн видео сайт дээр MP4-өөр тоглоно.

- Хичээлүүд «1-р анги монгол хэл» гэх мэт анги + хичээлийн playlist-д дугаарын дарааллаар орно.
  Тийм нэртэй playlist байхгүй бол скрипт шинээр үүсгэнэ.
- Google API аудит хийгдээгүй бол бичлэг **Private** болж түгжигдэнэ. Тэгвэл скриптийн хэвлэсэн
  Studio линкээр ороод **Public** болгоно.
- Нэвтрэлт: `client_secret.json` (Google Cloud → Google Auth Platform → Clients → Desktop app)
  болон `.youtube_token.json`. Хоёулаа git-д орохгүй. Токен хүчингүй болбол скрипт хөтөч нээж
  дахин нэвтрүүлнэ.
- Шаардлагатай сан: `python -m pip install --user google-api-python-client google-auth-oauthlib`

## Facebook хуудас

`publish.py` нь YouTube-д оруулсны дараа бичлэгийг Facebook хуудсанд **шууд** нийтэлнэ
(хуваарьтай болгох бол `fb.py` дахь `SCHEDULE = True`: өдөрт 1 пост, орой 20:00). Хичээлийн JSON-д `facebook_id`, `facebook_time` бичигдэнэ.

```
python publish.py --facebook   # YouTube-д орсон ч Facebook-д ороогүй хичээлүүдийг нийтэлнэ
python fb.py queue             # нийтэлсэн, хүлээгдэж буй постууд
python fb.py pin               # бүх хичээлийн линктэй pin постыг шинэчилнэ (нийтлэх бүрд автоматаар)
python fb.py check             # токен, хуудас
```

Нэг удаагийн тохиргоо: Meta апп үүсгээд `.fb_setup.json`-д `app_id`, `app_secret`, Graph API Explorer-оос
авсан `user_token`-оо бичнэ. Дараа нь `python fb.py setup` нь хугацаагүй Page token-ыг `.fb_token`-д хадгална.
Хоёр файл хоёулаа git-д орохгүй.

## YouTube-д гараар байршуулах

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
