(() => {
  "use strict";
  const LESSONS = window.LESSONS || [];
  const app = document.getElementById("app");
  const VOW = "аэиоуөүыяеёю";
  const SEMI = "й";

  // ------------------------------------------------ туслах
  const cls = (ch) => {
    const c = ch.toLowerCase();
    if (/[0-9]/.test(c)) return "n";
    if (VOW.includes(c)) return "v";
    if (SEMI.includes(c)) return "s";
    if (/\p{L}/u.test(c)) return "c";
    return "p";
  };
  const esc = (s) => s.replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
  const colorize = (text, hl) =>
    [...text].map((ch) => `<span class="${cls(ch)}${hl && ch.toLowerCase() === hl ? " hl-letter" : ""}">${esc(ch)}</span>`).join("");
  // хичээлийн жижиг хавтангууд: уншлагад үсэг, математикт тоо/тэмдэг
  const chipsOf = (l) => (l.type === "math" ? l.chips : [...l.letters]);
  const isNewChip = (l, tk) => (l.type === "math" ? l.new_chips.includes(tk) : l.new.includes(tk));
  const chipRow = (l, label) => `<div class="lesson-letters" aria-label="${label}">
      ${chipsOf(l).map((ch) => `<span class="mini${isNewChip(l, ch) ? " new" : ""}${ch.length > 1 ? " wide" : ""}">${colorize(ch)}</span>`).join("")}
    </div>`;
  // уншлагын тоглоомын сан: үг + асуулт, хүрэлцэхгүй бол үе
  const gamePool = (l) => (l.game.length >= 3 ? l.game : l.syllables.flat().map((s) => ({ w: s.t, a: s.a })));
  const READ_HAS = { syl: (l) => l.syllables.length, words: (l) => l.words.length,
                     sent: (l) => l.sentences.length, game: (l) => gamePool(l).length >= 3 };
  const tabsOf = (l) => (l.type === "math"
    ? MATH_TABS.filter((t) => t[0] !== "nums" || l.nums.length)
    : TABS.filter((t) => !READ_HAS[t[0]] || READ_HAS[t[0]](l)));
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const $ = (sel, root = app) => root.querySelector(sel);
  const $$ = (sel, root = app) => [...root.querySelectorAll(sel)];

  // ------------------------------------------------ дуу
  const player = new Audio();
  let pending = null;
  let token = 0;
  function playOne(src) {
    if (pending) { pending(false); pending = null; }
    return new Promise((res) => {
      const done = (ok) => { if (pending === res) pending = null; res(ok); };
      pending = res;
      player.onended = () => done(true);
      player.onerror = () => done(false);
      player.src = src;
      player.play().catch(() => done(false));
    });
  }
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  function stopAll() {
    token++;
    player.pause();
    if (pending) { pending(false); pending = null; }
  }
  // steps: [{a?, ms?, before?, after?}] - өөр дуу эхлэхэд тасарна
  async function playSeq(steps) {
    stopAll();
    const my = token;
    for (const st of steps) {
      if (my !== token) return false;
      if (st.before) st.before();
      if (st.a) await playOne(st.a); else await wait(st.ms || 0);
      if (my !== token) return false;
      if (st.after) st.after();
    }
    return true;
  }
  function clearMarks() {
    $$(".playing").forEach((e) => e.classList.remove("playing"));
    $$(".on").forEach((e) => e.classList.remove("on"));
    $$(".all").forEach((e) => e.classList.remove("all"));
    $$(".sy.arc").forEach((e) => e.classList.remove("arc"));
    $$(".word .hl-letter").forEach((e) => e.classList.remove("hl-letter"));
  }

  let ac;
  function tone(freqs, dur = 0.4, vol = 0.12) {
    try {
      ac = ac || new (window.AudioContext || window.webkitAudioContext)();
      const t0 = ac.currentTime;
      freqs.forEach((f, i) => {
        const o = ac.createOscillator();
        const g = ac.createGain();
        const st = t0 + i * 0.1;
        o.type = "sine";
        o.frequency.value = f;
        g.gain.setValueAtTime(0.0001, st);
        g.gain.exponentialRampToValueAtTime(vol, st + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, st + dur);
        o.connect(g).connect(ac.destination);
        o.start(st);
        o.stop(st + dur + 0.05);
      });
    } catch (e) { /* дуугүй орчин */ }
  }
  const sfxRight = () => tone([784, 1046, 1318]);
  const sfxWrong = () => tone([240, 190], 0.25, 0.08);
  const sfxTap = () => tone([660], 0.12, 0.06);

  // ------------------------------------------------ чиглүүлэлт
  const TABS = [
    ["video", "🎬", "Видео", "#e8534a"],
    ["letters", "🔤", "Үсэг", "#ef8a2a"],
    ["syl", "🧩", "Үе", "#3fa65a"],
    ["words", "📖", "Үг", "#2b67d8"],
    ["sent", "📝", "Өгүүлбэр", "#8c36aa"],
    ["game", "🎮", "Тоглоом", "#dd4479"],
  ];
  const MATH_TABS = [
    ["video", "🎬", "Видео", "#e8534a"],
    ["nums", "🔢", "Тоо", "#ef8a2a"],
    ["prob", "➕", "Бодлого", "#3fa65a"],
    ["game", "🎮", "Тоглоом", "#dd4479"],
  ];

  const BRAND = "Сурагч";
  // Бага анги: 1-5. Шинэ хичээл нэмэхдээ доорх жагсаалтад нэмнэ (түлхүүр нь JSON-ийн "subject").
  const GRADES = [1, 2, 3, 4, 5];
  const GRADE_COLORS = ["#d92b2b", "#ef8a2a", "#3fa65a", "#2b67d8", "#8c36aa"];
  const SUBJECTS = [
    ["mongol", "📖", "Монгол хэл"],
    ["math", "🔢", "Математик"],
    ["orchin", "🌱", "Хүн ба орчин"],
    ["baigal", "🔬", "Хүн ба байгаль"],
    ["niigem", "🏛️", "Хүн ба нийгэм"],
    ["english", "🇬🇧", "Англи хэл"],
    ["art", "🎨", "Дүрслэх урлаг, технологи"],
    ["music", "🎵", "Хөгжим"],
    ["pe", "⚽", "Биеийн тамир"],
  ];
  const subjectOf = (k) => SUBJECTS.find((s) => s[0] === k) || [k, "📘", k];
  const subjectName = (k) => subjectOf(k)[2];

  // Зочдын статистик (GoatCounter): #/1-math-hicheel_01/game -> /1-math-hicheel_01/game
  function track() {
    const path = "/" + location.hash.replace(/^#\/?/, "");
    const send = () => {
      try { window.goatcounter.count({ path, title: document.title }); } catch (e) { /* хаагдсан эсвэл ачаалаагүй */ }
    };
    if (window.goatcounter && window.goatcounter.count) send();
    else window.addEventListener("load", () => setTimeout(send, 0), { once: true });
  }

  function route() {
    stopAll();
    const [id, tab, sub] = location.hash.replace(/^#\/?/, "").split("/");
    const lesson = LESSONS.find((l) => l.id === id);
    if (id === "g" && GRADES.includes(Number(tab))) gradeView(Number(tab), sub);
    else if (id === "support" && SUPPORT.account) supportView();
    else if (lesson) lessonView(lesson, tabsOf(lesson).some((t) => t[0] === tab) ? tab : "video");
    else home();
    window.scrollTo(0, 0);
    track();
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------ дэмжих
  const SUPPORT = window.SUPPORT || {};
  const supportLink = document.getElementById("support-link");
  if (supportLink && SUPPORT.account) supportLink.hidden = false;

  function supportView() {
    document.title = `Дэмжих | ${BRAND}`;
    const rows = [
      ["Банк", SUPPORT.bank],
      ["Данс", SUPPORT.account, true],
      ["IBAN", SUPPORT.iban, true],
      ["Хүлээн авагч", SUPPORT.name],
      ["Гүйлгээний утга", SUPPORT.note, true],
    ].filter((r) => r[1]);
    app.innerHTML = `
      <div class="lesson-head">
        <a class="btn ghost back" href="#/">← Нүүр</a>
        <h1>💛 Дэмжих <small>Эцэг эх, том хүмүүст</small></h1>
      </div>
      <div class="support">
        <p>«${BRAND}» сайтын хичээл, видео бүгд үнэгүй. Шинэ хичээл бэлтгэхэд дэмжлэг үзүүлэхийг хүсвэл доорх дансаар хандив өгч болно. Хэмжээ хамаагүй, баярлалаа!</p>
        <dl class="bank">
          ${rows.map(([k, v, copy]) => `
            <div class="bank-row">
              <dt>${esc(k)}</dt>
              <dd><span>${esc(v)}</span>${copy ? `<button class="copy" data-copy="${esc(v)}">Хуулах</button>` : ""}</dd>
            </div>`).join("")}
        </dl>
      </div>`;
    $$(".copy").forEach((b) => b.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = "Хуулсан ✓"; }
      catch (e) { b.textContent = "Гараар хуулна уу"; }
      setTimeout(() => { b.textContent = "Хуулах"; }, 1800);
    }));
  }

  // ------------------------------------------------ нүүр
  // ------------------------------------------------ явц (энэ хөтөч дээр л хадгалагдана)
  const store = {
    get(k, d) { try { const v = localStorage.getItem("suragch." + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("suragch." + k, JSON.stringify(v)); } catch (e) { /* хувийн цонх */ } },
  };
  const seenSet = () => new Set(store.get("seen", []));
  const markSeen = (id) => { const s = seenSet(); if (!s.has(id)) { s.add(id); store.set("seen", [...s]); } };
  const byNumber = (a, b) => (a.number || 0) - (b.number || 0);
  const subjectLessons = (g, k) => LESSONS.filter((l) => l.grade === g && l.subject === k).sort(byNumber);
  // дараагийн хичээл: үзсэн хамгийн сүүлийн хичээлийн дараах, үзээгүй эхнийх
  const nextLesson = (list, seen) => {
    let last = -1;
    list.forEach((l, i) => { if (seen.has(l.id)) last = i; });
    return list.slice(last + 1).find((l) => !seen.has(l.id)) || list.find((l) => !seen.has(l.id)) || null;
  };
  const SUBJECT_COLORS = { mongol: "#2b67d8", math: "#3fa65a", orchin: "#ef8a2a", baigal: "#0b9aa8",
                           niigem: "#8c36aa", english: "#d92b2b", art: "#dd4479", music: "#e0a100", pe: "#1f4fb0" };

  // ------------------------------------------------ хичээлийн карт
  function cardGlyph(l) {
    if (l.glyph) {
      return `<span class="glyph${l.glyph.length > 3 ? " small" : ""}">${[...l.glyph].map((ch) => (ch === " " ? " " : colorize(ch))).join("")}</span>`;
    }
    if (l.type === "math") {
      const nw = l.new_chips || [];
      const c = nw.length && nw.every((x) => /^[0-9]+$/.test(x)) ? nw : l.chips;   // шинэ тоо, эсвэл илэрхийлэл
      const txt = c.length <= 5 ? c.join(" ") : `${c[0]}–${c[c.length - 1]}`;
      return `<span class="glyph${txt.length > 5 ? " small" : ""}">${[...txt].map((ch) => (ch === " " ? " " : colorize(ch))).join("")}</span>`;
    }
    const nw = l.new || "";
    return `<span class="glyph">${nw ? colorize(nw.toUpperCase() + nw) : colorize([...l.letters].slice(-1)[0] || "")}</span>`;
  }
  const LETTER_NAMES = { "й": "Хагас и" };
  const cardCaption = (l) => (l.type === "math" ? l.topic
    : l.new ? `${LETTER_NAMES[l.new] || l.new.toUpperCase()} үсэг` : l.topic || l.title || "");

  function lessonCard(l, opts = {}) {
    const cls2 = ["tile", "lcard", opts.seen ? "seen" : "", opts.next ? "next" : ""].join(" ").trim();
    return `<li><a class="${cls2}" href="#/${l.id}" style="--sc:${SUBJECT_COLORS[l.subject] || "#56608a"}"
        aria-label="${l.number}-р хичээл: ${esc(cardCaption(l))}${opts.seen ? ", үзсэн" : ""}">
      <span class="lnum">${l.number}</span>
      ${opts.seen ? `<span class="mark" aria-hidden="true">✓</span>` : ""}
      ${opts.next ? `<span class="flag">Дараагийнх</span>` : ""}
      ${cardGlyph(l)}
      <span class="lcap">${esc(cardCaption(l))}</span>
      ${opts.place ? `<span class="lsub">${l.grade}-р анги, ${subjectName(l.subject)}</span>` : ""}
    </a></li>`;
  }

  function home() {
    document.title = `${BRAND} | Бага ангийн хичээл`;
    const h1 = [...BRAND].map((ch, i) =>
      `<span class="tw ${cls(ch)}" style="animation-delay:${i * 60}ms">${esc(ch)}</span>`).join("");
    const seen = seenSet();
    const latest = LESSONS.slice().sort((a, b) => (b.added || 0) - (a.added || 0) || b.number - a.number).slice(0, 4);
    // үргэлжлүүлэх: хамгийн сүүлд үзсэн хичээлийн хичээлийн дараагийнх
    const lastId = store.get("last", "");
    const last = LESSONS.find((l) => l.id === lastId);
    const cont = last ? nextLesson(subjectLessons(last.grade, last.subject), seen) : null;
    app.innerHTML = `
      <header class="hero">
        <h1 aria-label="${BRAND}">${h1}</h1>
        <p>Бага ангийн хүүхдэд зориулсан хичээлүүд</p>
      </header>
      ${cont ? `<a class="continue tile" href="#/${cont.id}" style="--sc:${SUBJECT_COLORS[cont.subject] || "#56608a"}">
          ${cardGlyph(cont)}
          <span><b>Үргэлжлүүлэх</b><br>${subjectName(cont.subject)}, ${cont.number}-р хичээл: ${esc(cardCaption(cont))}</span>
          <span class="go" aria-hidden="true">▶</span>
        </a>` : ""}
      <h2 class="sec-title">Ангиа сонгоорой</h2>
      <nav class="grade-grid" aria-label="Ангиуд">
        ${GRADES.map((g, i) => {
          const n = LESSONS.filter((l) => l.grade === g).length;
          return `<a class="grade-card${n ? "" : " empty"}" href="#/g/${g}" style="--gc:${GRADE_COLORS[i]}">
            <span class="gnum">${g}</span><span class="glbl">-р анги</span>
            <span class="gcount">${n ? `${n} хичээл` : "Удахгүй"}</span>
          </a>`;
        }).join("")}
      </nav>
      ${latest.length ? `<h2 class="sec-title">Шинэ хичээлүүд</h2>
        <ul class="lesson-grid">${latest.map((l) => lessonCard(l, { place: true, seen: seen.has(l.id) })).join("")}</ul>` : ""}`;
  }

  function gradeView(g, subj) {
    document.title = `${g}-р анги | ${BRAND}`;
    const inGrade = LESSONS.filter((l) => l.grade === g);
    const keys = [...new Set([...SUBJECTS.map((s) => s[0]), ...inGrade.map((l) => l.subject)])]
      .filter((k) => inGrade.some((l) => l.subject === k));
    const saved = store.get(`subj${g}`, "");
    const cur = keys.includes(subj) ? subj : keys.includes(saved) ? saved : keys[0];
    if (cur) store.set(`subj${g}`, cur);
    const list = cur ? subjectLessons(g, cur) : [];
    const seen = seenSet();
    const nxt = nextLesson(list, seen);
    const done = list.filter((l) => seen.has(l.id)).length;
    app.innerHTML = `
      <div class="lesson-head">
        <a class="btn ghost back" href="#/">← Нүүр</a>
        <h1>${g}-р анги</h1>
      </div>
      ${keys.length ? `<div class="tabs subj-tabs" role="tablist" aria-label="Хичээлүүд">
        ${keys.map((k) => {
          const [, ico, name] = subjectOf(k);
          return `<a class="tab" role="tab" href="#/g/${g}/${k}" aria-selected="${k === cur}" style="--tabc:${SUBJECT_COLORS[k] || "#56608a"}">
            <span class="ico" aria-hidden="true">${ico}</span><span>${name}</span><span class="cnt">${inGrade.filter((l) => l.subject === k).length}</span>
          </a>`;
        }).join("")}
      </div>
      <div class="subj-head">
        <p class="progress-note">${done ? `${list.length} хичээлээс ${done}-ийг үзсэн` : `${list.length} хичээл. 1-р хичээлээс эхлээрэй.`}</p>
        ${nxt ? `<a class="btn" href="#/${nxt.id}">▶ ${done ? "Үргэлжлүүлэх" : "Эхлэх"}: ${nxt.number}-р хичээл</a>` : ""}
      </div>
      <ul class="lesson-grid">${list.map((l) => lessonCard(l, { seen: seen.has(l.id), next: nxt && l.id === nxt.id })).join("")}</ul>` : ""}
      <p class="soon">${keys.length ? "Бусад хичээлүүд удахгүй нэмэгдэнэ." : "Энэ ангийн хичээлүүд удахгүй нэмэгдэнэ."}</p>`;
  }

  // ------------------------------------------------ хичээл
  function lessonView(l, tab) {
    const what = l.topic || [...l.letters].join(" ");
    document.title = `${subjectName(l.subject)}, ${l.number}-р хичээл: ${what} | ${BRAND}`;
    app.innerHTML = `
      <div class="lesson-head">
        <a class="btn ghost back" href="#/g/${l.grade}/${l.subject}">← ${l.grade}-р анги</a>
        <h1>${l.number}-р хичээл <small>${l.grade}-р анги, ${subjectName(l.subject)}${l.topic ? `: ${esc(l.topic)}` : ""}</small></h1>
        ${chipRow(l, l.type === "math" ? l.topic : "Үсгүүд")}
      </div>
      <div class="tabs" role="tablist">
        ${tabsOf(l).map(([k, ico, lbl, col]) => `
          <button class="tab" role="tab" aria-selected="${k === tab}" data-tab="${k}" style="--tabc:${col}">
            <span class="ico" aria-hidden="true">${ico}</span><span class="lbl">${lbl}</span>
          </button>`).join("")}
      </div>
      <section class="panel" role="tabpanel"></section>`;
    $$(".tab").forEach((b) => b.addEventListener("click", () => { location.hash = `#/${l.id}/${b.dataset.tab}`; }));
    const panel = $(".panel");
    markSeen(l.id);
    store.set("last", l.id);
    const sibs = subjectLessons(l.grade, l.subject);
    const k = sibs.findIndex((x) => x.id === l.id);
    const prev = sibs[k - 1], next = sibs[k + 1];
    if (prev || next) {
      panel.insertAdjacentHTML("afterend", `<nav class="lesson-nav" aria-label="Хичээлүүд">
        ${prev ? `<a class="btn ghost" href="#/${prev.id}">← ${prev.number}-р хичээл</a>` : "<span></span>"}
        <a class="btn ghost" href="#/g/${l.grade}/${l.subject}">☰ Бүх хичээл</a>
        ${next ? `<a class="btn" href="#/${next.id}">${next.number}-р хичээл →</a>` : "<span></span>"}
      </nav>`);
    }
    const panels = l.type === "math"
      ? { video: videoPanel, nums: numsPanel, prob: probPanel, game: mathGamePanel }
      : { video: videoPanel, letters: lettersPanel, syl: sylPanel, words: wordsPanel, sent: sentPanel, game: gamePanel };
    panels[tab](panel, l);
  }

  // нийтлэг: data-a товч дарахад дуу тоглуулна
  function bindAudio(root) {
    $$("[data-a]", root).forEach((el) => el.addEventListener("click", () => {
      clearMarks();
      el.classList.add("playing");
      playSeq([{ a: el.dataset.a }]).then(() => el.classList.remove("playing"));
    }));
  }

  function videoPanel(p, l) {
    let player = `<p class="hint">Энэ хичээлийн видео одоогоор алга байна.</p>`;
    if (l.youtube_id) {
      player = `<div class="video-wrap"><iframe src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(l.youtube_id)}?rel=0"
        title="${l.number}-р хичээлийн видео" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture; fullscreen" allowfullscreen></iframe></div>`;
    } else if (l.video) {
      player = `<div class="video-wrap"><video controls preload="metadata" playsinline ${l.poster ? `poster="${l.poster}"` : ""} src="${l.video}"></video></div>`;
    }
    p.innerHTML = `<h2>Видео хичээл</h2>
      <p class="hint">Видеог үзээд, 🗣️ тэмдэг гарахад чангаар давтаарай.</p>${player}`;
  }

  function lettersPanel(p, l) {
    p.innerHTML = `<h2>Үсгээ давтъя</h2>
      <p class="hint">Үсэг дээр дарж сонсоорой.</p>
      <div class="letter-grid">
        ${l.letter_cards.map((c) => `
          <div class="letter-card">
            <button class="tile big" data-a="${c.a}" aria-label="${c.ch} үсэг">
              ${colorize(c.ch.toUpperCase() + c.ch)}
              ${l.new.includes(c.ch) ? `<span class="badge">⭐ Шинэ</span>` : ""}
            </button>
            ${c.example ? `<button class="tile ex" data-a="${c.ea}" aria-label="${c.example}">
              ${c.emoji ? `<span class="em" aria-hidden="true">${c.emoji}</span>` : ""}<span>${c.listen
                ? [...c.example].map((x) => (l.letters.includes(x.toLowerCase()) ? colorize(x, c.ch) : `<span class="dim">${esc(x)}</span>`)).join("")
                : colorize(c.example, c.ch)}</span>
            </button>` : ""}
          </div>`).join("")}
      </div>
      ${(l.listen || []).length ? `<h2 class="listen-title">Сонсоод олъё</h2>
        <p class="hint">Үг дээр дарж сонсоод, ${esc(l.new.toUpperCase())} үсгийг олоорой.</p>
        <div class="word-grid">
          ${l.listen.map((w, i) => `
            <button class="tile word-card listen-card" data-li="${i}" aria-label="${esc(w.w)}">
              <span class="em" aria-hidden="true">${w.emoji || ""}</span>
              <span class="word">${[...w.w].map((ch, k) => `<span class="${w.hl.includes(k) ? `${cls(ch)} lt` : "dim"}">${esc(ch)}</span>`).join("")}</span>
            </button>`).join("")}
        </div>` : ""}`;
    $$(".listen-card", p).forEach((b) => b.addEventListener("click", () => {
      const w = l.listen[b.dataset.li];
      clearMarks();
      const lts = $$(".lt", b);
      const steps = [{ before: () => b.classList.add("playing"), a: w.a }, { ms: 250 }];
      lts.forEach((x) => steps.push({ before: () => x.classList.add("hl-letter"), ms: 450 }));
      steps.push({ ms: 900, after: () => { b.classList.remove("playing"); lts.forEach((x) => x.classList.remove("hl-letter")); } });
      playSeq(steps);
    }));
    bindAudio(p);
  }

  function sylPanel(p, l) {
    const map = {};
    l.syllables.flat().forEach((s) => { map[s.t] = s.a; });
    p.innerHTML = `<h2>Үе уншъя</h2>
      <p class="hint">Үе дээр дарж сонсоод, давтаж хэлээрэй.</p>
      ${l.syllables.map((g) => `<div class="syl-group">
        ${g.map((s) => `<button class="tile syl" data-a="${s.a}">${colorize(s.t)}</button>`).join("")}
      </div>`).join("")}
      <div class="builder">
        <h2>Үе бүтээе</h2>
        <p class="hint">Хоёр үсэг сонгоод, ямар үе болохыг сонсоорой.</p>
        <div class="slots" aria-live="polite">
          <span class="slot"></span><span class="plus" aria-hidden="true">+</span><span class="slot"></span>
        </div>
        <div class="builder-msg"></div>
        <div class="keys">
          ${[...l.letters].map((ch) => `<button class="tile key" data-k="${ch}">${colorize(ch)}</button>`).join("")}
          <button class="tile key clear" data-k="">Арилгах</button>
        </div>
      </div>`;
    bindAudio(p);
    let picked = [];
    const slots = $(".slots", p);
    const msg = $(".builder-msg", p);
    const draw = () => {
      $$(".slot", p).forEach((s, i) => { s.innerHTML = picked[i] ? colorize(picked[i]) : ""; s.classList.toggle("filled", !!picked[i]); });
    };
    $$(".key", p).forEach((k) => k.addEventListener("click", () => {
      slots.classList.remove("ok", "bad");
      msg.textContent = "";
      if (!k.dataset.k) { picked = []; draw(); return; }
      if (picked.length >= 2) picked = [];
      picked.push(k.dataset.k);
      draw();
      if (picked.length < 2) { sfxTap(); return; }
      const s = picked.join("");
      if (map[s]) {
        slots.classList.add("ok");
        msg.innerHTML = `Сайн байна! ${colorize(s)}`;
        playSeq([{ a: map[s] }]);
      } else {
        void slots.offsetWidth;
        slots.classList.add("bad");
        sfxWrong();
        msg.textContent = "Ийм үе байхгүй. Өөр үсэг сонгоорой.";
      }
    }));
  }

  function wordMarkup(w) {
    return `<span class="word">${w.syl.map((s, k) => `<span class="sy" data-k="${k}">${colorize(s.t)}</span>`).join("")}</span>`;
  }

  function readWordSteps(card, w) {
    const word = $(".word", card);
    const sys = $$(".sy", word);
    const steps = [];
    if (w.syl.length > 1) {
      w.syl.forEach((s, k) => steps.push({
        before: () => sys[k].classList.add("on"),
        a: s.a,
        after: () => { sys[k].classList.remove("on"); sys[k].classList.add("arc"); },
      }, { ms: 150 }));
    } else {
      $$("span span", word).forEach((ch) => steps.push({
        before: () => ch.classList.add("hl-letter"),
        ms: 420,
        after: () => ch.classList.remove("hl-letter"),
      }));
    }
    steps.push({ before: () => { word.classList.add("all"); sys.forEach((s) => s.classList.add("arc")); }, a: w.a },
      { ms: 700, after: () => { word.classList.remove("all"); card.classList.add("done"); } });
    return steps;
  }

  function wordsPanel(p, l) {
    p.innerHTML = `<h2>Үг уншъя</h2>
      <p class="hint">Үг дээр дарвал үеэр нь уншаад, дараа нь бүтэн уншина.</p>
      <div class="word-grid">
        ${l.words.map((w, i) => `
          <div class="tile word-card" data-i="${i}">
            <button class="word-btn" aria-label="${w.w}">
              <span class="em${w.emoji ? "" : " none"}" aria-hidden="true">${w.emoji || "·"}</span>
              ${wordMarkup(w)}
            </button>
            ${w.explain ? `<button class="explain" data-x="${i}">💬 Утга нь</button>` : ""}
          </div>`).join("")}
      </div>`;
    $$(".word-card", p).forEach((card) => {
      const w = l.words[card.dataset.i];
      $(".word-btn", card).addEventListener("click", () => { clearMarks(); playSeq(readWordSteps(card, w)); });
      const x = $(".explain", card);
      if (x) x.addEventListener("click", () => { clearMarks(); x.classList.add("playing"); playSeq([{ a: w.xa }]).then(() => x.classList.remove("playing")); });
    });
  }

  function sentPanel(p, l) {
    const plain = l.sentences.some((s) => !s.story);
    p.innerHTML = `${plain ? `<h2>Өгүүлбэр уншъя</h2>
      <p class="hint">▶ дээр дарвал үг үгээр нь, дараа нь бүтэн өгүүлбэрийг уншина.</p>` : ""}
      ${l.sentences.map((s, i) => `
        ${s.story && !(l.sentences[i - 1] || {}).story ? `<h2 class="story-title">${l.story_emoji ? `<span aria-hidden="true">${l.story_emoji}</span> ` : ""}Өгүүллэг: ${colorize(l.story_title || "")}</h2>
          <p class="hint">Өгүүлбэр бүрийг ▶ дарж сонсоод, дагаж уншаарай.</p>` : ""}
        <div class="sentence" data-i="${i}">
          <button class="tile play" aria-label="Өгүүлбэрийг унших">▶</button>
          ${s.words.map((w) => `<button class="sw" data-a="${w.a}">${colorize(w.t)}</button>`).join("")}
          ${s.emoji ? `<span class="em" aria-hidden="true">${s.emoji}</span>` : ""}
        </div>`).join("")}`;
    bindAudio(p);
    $$(".sentence", p).forEach((row) => {
      const s = l.sentences[row.dataset.i];
      const btns = $$(".sw", row);
      $(".play", row).addEventListener("click", () => {
        clearMarks();
        const steps = [];
        s.words.forEach((w, k) => steps.push({ before: () => btns[k].classList.add("on"), a: w.a, after: () => btns[k].classList.remove("on") }, { ms: 200 }));
        steps.push({ ms: 250 }, { before: () => row.classList.add("all"), a: s.a }, { ms: 900, after: () => row.classList.remove("all") });
        playSeq(steps);
      });
    });
  }

  function gamePanel(p, l) {
    const TOTAL = 6;
    let pool = gamePool(l);
    let order = [], round = 0, score = 0, missed = false, target = null;

    const start = () => {
      order = shuffle(pool);
      while (order.length < TOTAL) order = order.concat(shuffle(pool));
      order = order.slice(0, TOTAL);
      round = 0; score = 0;
      next();
    };
    const stars = () => "⭐".repeat(score) + "☆".repeat(TOTAL - score);
    const next = () => {
      if (round >= TOTAL) return finish();
      target = order[round];
      missed = false;
      const opts = shuffle([target, ...shuffle(pool.filter((x) => x.w !== target.w)).slice(0, 2)]);
      p.innerHTML = `<div class="game">
        <h2>Сонсоод ол</h2>
        <div class="score" aria-label="Оноо ${score}">${stars()}</div>
        <button class="listen pulse" aria-label="Дахин сонсох">🔊</button>
        <div class="choices">
          ${opts.map((o) => `<button class="tile choice" data-w="${esc(o.w)}">${colorize(o.w)}</button>`).join("")}
        </div>
      </div>`;
      const say = () => playSeq([{ a: target.a }]);
      $(".listen", p).addEventListener("click", say);
      $$(".choice", p).forEach((b) => b.addEventListener("click", () => {
        if (b.dataset.w === target.w) {
          b.classList.add("right");
          if (!missed) score++;
          $(".score", p).textContent = stars();
          sfxRight();
          $$(".choice", p).forEach((x) => { x.disabled = true; });
          round++;
          setTimeout(next, 1100);
        } else {
          missed = true;
          b.classList.remove("wrong");
          void b.offsetWidth;
          b.classList.add("wrong");
          sfxWrong();
          setTimeout(say, 450);
        }
      }));
      say();
    };
    const finish = () => {
      const msg = score === TOTAL ? "Гайхалтай! Бүгдийг нь зөв оллоо!" : score >= TOTAL / 2 ? "Сайн байна!" : "Дахиад хичээгээрэй!";
      p.innerHTML = `<div class="game">
        <div class="result"><span class="stars">${stars()}</span>${msg}</div>
        <p class="hint">Зөв: ${score} / ${TOTAL}</p>
        <button class="btn again">↻ Дахин тоглох</button>
      </div>`;
      sfxRight();
      $(".again", p).addEventListener("click", start);
    };
    p.innerHTML = `<div class="game">
      <h2>Сонсоод ол</h2>
      <p class="hint">Үгийг сонсоод, зөв бичигдсэн үгийг дараарай.</p>
      <button class="btn startg">▶ Эхлэх</button>
    </div>`;
    $(".startg", p).addEventListener("click", start);
  }

  // ------------------------------------------------ математик
  const objs = (e, n) => `<span class="objs" aria-hidden="true">${Array.from({ length: n }, (_, i) =>
    `<span class="ob" style="animation-delay:${i * 90}ms">${e}</span>`).join("")}</span>`;

  // эгнээ: ring - тэмдэглэх зүйлийн индекс
  const rowHtml = (row, ring) => `<span class="objs row" aria-hidden="true">${row.map((e, i) =>
    `<span class="ob${i === ring ? " ring" : ""}" style="animation-delay:${i * 70}ms">${e}</span>`).join("")}</span>`;

  function ordPanel(p, l) {
    p.innerHTML = `<h2>Дэс дугаар</h2>
      <p class="hint">Карт дээр дарж сонсоорой. Зүүн талаас нь тоолно.</p>
      <div class="num-grid ord-grid">
        ${l.nums.map((c, i) => `
          <button class="tile num-card" data-i="${i}" aria-label="${c.word}">
            <span class="num-big">${colorize(`${c.n}-р`)}</span>
            <span class="num-word">${esc(c.word)}</span>
            <span class="num-objs">${rowHtml(c.row, c.n - 1)}</span>
          </button>`).join("")}
      </div>`;
    $$(".num-card", p).forEach((b) => b.addEventListener("click", () => {
      const c = l.nums[b.dataset.i];
      clearMarks();
      const obs = $$(".ob", b);
      const steps = [{ before: () => b.classList.add("playing") }];
      for (let k = 0; k < c.n; k++) {
        steps.push({ before: () => obs[k].classList.add("on"), a: l.ord_audio[k + 1] }, { ms: 120 });
      }
      steps.push({ ms: 400, after: () => { b.classList.remove("playing"); obs.forEach((o) => o.classList.remove("on")); } });
      playSeq(steps);
    }));
  }

  function numsPanel(p, l) {
    if (l.nums.length && l.nums[0].ord) return ordPanel(p, l);
    p.innerHTML = `<h2>Тоотой танилцъя</h2>
      <p class="hint">Тоон дээр дарж сонсоод, зүйлсийг хамт тоолоорой.</p>
      <div class="num-grid">
        ${l.nums.map((c, i) => `
          <button class="tile num-card" data-i="${i}" aria-label="${c.n}, ${c.word}">
            <span class="num-big">${colorize(String(c.n))}</span>
            <span class="num-word">${esc(c.word)}</span>
            <span class="num-objs">${c.n ? objs(c.emoji, c.n) : `<span class="objs"><span class="ob">${c.emoji}</span></span>`}</span>
          </button>`).join("")}
      </div>`;
    $$(".num-card", p).forEach((b) => b.addEventListener("click", () => {
      const c = l.nums[b.dataset.i];
      clearMarks();
      const obs = $$(".ob", b);
      const steps = [{ before: () => b.classList.add("playing"), a: l.num_audio[c.n] }, { ms: 250 }];
      for (let k = 0; k < c.n; k++) {
        steps.push({ before: () => obs[k].classList.add("on"), a: l.num_audio[k + 1] }, { ms: 120 });
      }
      if (c.sa) steps.push({ ms: 200 }, { a: c.sa });
      steps.push({ ms: 400, after: () => { b.classList.remove("playing"); obs.forEach((o) => o.classList.remove("on")); } });
      playSeq(steps);
    }));
  }

  // "2 + 1 = ?" илэрхийлэл. hidden: асуултын тэмдгээр солих байрлал
  const tokHtml = (t, hidden) => t.map((tk, i) => {
    if (i === hidden) return `<span class="tok q${/^[0-9]/.test(tk) ? "" : " sgn"}">?</span>`;
    if (/^[0-9]+-р$/.test(tk)) return `<span class="tok wide">${colorize(tk)}</span>`;
    if (/^\p{L}{2,}$/u.test(tk)) return `<span class="op word">${esc(tk)}</span>`;
    return /^[0-9]+$/.test(tk) ? `<span class="tok">${colorize(tk)}</span>` : `<span class="op">${esc(tk)}</span>`;
  }).join("");

  function probPanel(p, l) {
    p.innerHTML = `<h2>Бодлого бодъё</h2>
      <p class="hint">Хариултаа чангаар хэлээд, <b>?</b> дээр дарж шалгаарай.</p>
      <div class="prob-list">
        ${l.problems.map((q, i) => `
          <button class="tile prob" data-i="${i}" aria-label="Хариуг харах">
            ${q.emoji ? `<span class="em" aria-hidden="true">${q.emoji}</span>` : ""}
            ${q.row ? `<span class="prob-row"><span class="dir">${q.right ? "⬅️" : "➡️"}</span>${rowHtml(q.row, q.ring)}</span>` : ""}
            <span class="expr">${tokHtml(q.t, q.h)}</span>
          </button>`).join("")}
      </div>`;
    $$(".prob", p).forEach((row) => row.addEventListener("click", () => {
      const q = l.problems[row.dataset.i];
      const tk = $(".tok.q", row);
      if (tk) {
        tk.classList.remove("q");
        tk.classList.add("ok");
        tk.innerHTML = /^[0-9]/.test(q.t[q.h]) ? colorize(q.t[q.h]) : esc(q.t[q.h]);
        row.classList.add("done");
        sfxRight();
      }
      clearMarks();
      setTimeout(() => playSeq([{ a: q.a }]), tk ? 350 : 0);
    }));
  }

  function mathGamePanel(p, l) {
    const TOTAL = 6;
    const EMO = ["🍎", "🐟", "⭐", "🐥", "🎈", "🌸", "🍓", "🐞", "🍪", "🚗"];
    const max = l.game.max;
    const rnd = (a, b) => a + Math.floor(Math.random() * (b - a + 1));
    const TITLE = { count: "Хэд байна?", add: "Нэмж бодоорой", sub: "Хасаж бодоорой", compare: "Тэмдгээ ол",
                    split: "Хэд дутуу вэ?", mix: "Бодоод ол", ordinal: "Хэд дэх вэ?" };
    let round = 0, score = 0, missed = false;

    function numOpts(ans, lo, hi) {
      const set = new Set([ans]);
      let guard = 0;
      while (set.size < 3 && guard++ < 50) set.add(Math.max(lo, Math.min(hi, ans + rnd(-3, 3))));
      for (let v = lo; set.size < 3; v++) set.add(v);
      return shuffle([...set].map(String));
    }
    const make = () => {
      let kind = l.game.kind;
      if (kind === "mix") kind = ["add", "sub", "compare"][rnd(0, 2)];
      const e = EMO[rnd(0, EMO.length - 1)];
      if (kind === "ordinal") {
        const k = rnd(4, Math.max(4, Math.min(8, max))), i = rnd(0, k - 1);
        const pool = shuffle(EMO);
        const row = Array.from({ length: k }, (_, j) => pool[j % pool.length]);
        const set = new Set([i + 1]);
        while (set.size < 3) set.add(Math.max(1, Math.min(k, i + 1 + rnd(-2, 2))));
        for (let v = 1; set.size < 3; v++) set.add(v);
        const ans = `${i + 1}-р`;
        return { pic: `<span class="dir">➡️</span>${rowHtml(row, i)}`, q: tokHtml([ans], 0), ans,
                 opts: shuffle([...set].map((v) => `${v}-р`)), audio: l.ord_q_audio, say: l.ord_audio[i + 1] };
      }
      if (kind === "count") {
        const n = rnd(1, max);
        return { pic: objs(e, n), q: "", ans: String(n), opts: numOpts(n, 1, max), audio: l.q_audio };
      }
      if (kind === "add") {
        const c = rnd(2, max), a = rnd(1, c - 1), b = c - a;
        return { pic: `${objs(e, a)}<span class="op">+</span>${objs(e, b)}`,
                 q: tokHtml([String(a), "+", String(b), "=", String(c)], 4), ans: String(c), opts: numOpts(c, 0, max) };
      }
      if (kind === "sub") {
        const a = rnd(2, max), b = rnd(1, a), c = a - b;
        return { pic: objs(e, a), q: tokHtml([String(a), "−", String(b), "=", String(c)], 4), ans: String(c),
                 opts: numOpts(c, 0, max), strike: b };
      }
      if (kind === "compare") {
        const a = rnd(1, max), b = Math.random() < 0.25 ? a : rnd(1, max);
        const sgn = a < b ? "<" : a > b ? ">" : "=";
        return { pic: `${objs(e, a)}<span class="op">?</span>${objs(e, b)}`, q: tokHtml([String(a), sgn, String(b)], 1),
                 ans: sgn, opts: ["<", "=", ">"], sym: true };
      }
      const n = rnd(2, max), a = rnd(1, n - 1), b = n - a;   // тоог задлах
      return { pic: objs(e, n), q: tokHtml([String(n), "→", String(a), "ба", String(b)], 4), ans: String(b),
               opts: numOpts(b, 1, n - 1) };
    };
    const stars = () => "⭐".repeat(score) + "☆".repeat(TOTAL - score);
    const start = () => { round = 0; score = 0; next(); };
    const next = () => {
      if (round >= TOTAL) return finish();
      missed = false;
      const g = make();
      p.innerHTML = `<div class="game mgame">
        <h2>${TITLE[l.game.kind]}</h2>
        <div class="score" aria-label="Оноо ${score}">${stars()}</div>
        <div class="pic">${g.pic}</div>
        ${g.q ? `<div class="expr big">${g.q}</div>` : ""}
        <div class="choices">
          ${g.opts.map((o) => `<button class="tile choice${g.sym ? " sym" : ""}" data-v="${esc(o)}">${g.sym ? esc(o) : colorize(o)}</button>`).join("")}
        </div>
      </div>`;
      if (g.strike) $$(".pic .ob", p).slice(-g.strike).forEach((o) => o.classList.add("gone"));
      if (g.audio) playSeq([{ a: g.audio }]);
      $$(".choice", p).forEach((b) => b.addEventListener("click", () => {
        if (b.dataset.v === g.ans) {
          b.classList.add("right");
          if (!missed) score++;
          $(".score", p).textContent = stars();
          const q = $(".expr .q", p);
          if (q) { q.classList.remove("q"); q.classList.add("ok"); q.innerHTML = g.sym ? esc(g.ans) : colorize(g.ans); }
          sfxRight();
          $$(".choice", p).forEach((x) => { x.disabled = true; });
          setTimeout(() => playSeq([{ a: g.say || (g.sym ? l.cmp_audio[g.ans] : l.num_audio[Number(g.ans)]) }]), 300);
          round++;
          setTimeout(next, 1800);
        } else {
          missed = true;
          b.classList.remove("wrong");
          void b.offsetWidth;
          b.classList.add("wrong");
          sfxWrong();
        }
      }));
    };
    const finish = () => {
      const msg = score === TOTAL ? "Гайхалтай! Бүгдийг нь зөв бодлоо!" : score >= TOTAL / 2 ? "Сайн байна!" : "Дахиад хичээгээрэй!";
      p.innerHTML = `<div class="game">
        <div class="result"><span class="stars">${stars()}</span>${msg}</div>
        <p class="hint">Зөв: ${score} / ${TOTAL}</p>
        <button class="btn again">↻ Дахин тоглох</button>
      </div>`;
      sfxRight();
      $(".again", p).addEventListener("click", start);
    };
    p.innerHTML = `<div class="game">
      <h2>${TITLE[l.game.kind]}</h2>
      <p class="hint">Зургийг хараад, зөв хариултыг дараарай. Тоглох болгонд шинэ бодлого гарна.</p>
      <button class="btn startg">▶ Эхлэх</button>
    </div>`;
    $(".startg", p).addEventListener("click", start);
  }

  route();
})();
