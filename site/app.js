(() => {
  "use strict";
  const LESSONS = window.LESSONS || [];
  const app = document.getElementById("app");
  const VOW = "аэиоуөүыяеёю";
  const SEMI = "й";

  // ------------------------------------------------ туслах
  const cls = (ch) => {
    const c = ch.toLowerCase();
    if (VOW.includes(c)) return "v";
    if (SEMI.includes(c)) return "s";
    if (/\p{L}/u.test(c)) return "c";
    return "p";
  };
  const esc = (s) => s.replace(/[&<>"]/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]));
  const colorize = (text, hl) =>
    [...text].map((ch) => `<span class="${cls(ch)}${hl && ch.toLowerCase() === hl ? " hl-letter" : ""}">${esc(ch)}</span>`).join("");
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

  function route() {
    stopAll();
    const [id, tab] = location.hash.replace(/^#\/?/, "").split("/");
    const lesson = LESSONS.find((l) => l.id === id);
    if (id === "g" && GRADES.includes(Number(tab))) gradeView(Number(tab));
    else if (lesson) lessonView(lesson, TABS.some((t) => t[0] === tab) ? tab : "video");
    else home();
    window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------ нүүр
  function lessonRow(l, showPlace) {
    const body = l.letters
      ? `<div class="lesson-letters" aria-label="Үсгүүд: ${[...l.letters].join(", ")}">
          ${[...l.letters].map((ch) => `<span class="mini${l.new.includes(ch) ? " new" : ""}">${colorize(ch)}</span>`).join("")}
        </div>`
      : `<div class="lesson-title">${esc(l.title || "")}</div>`;
    return `
      <li class="lesson-row">
        <span class="lesson-num" aria-hidden="true">${l.number}</span>
        <div>${body}${showPlace ? `<small>${l.grade}-р анги, ${subjectName(l.subject)}</small>` : ""}</div>
        <a class="btn" href="#/${l.id}">▶ ${l.number}-р хичээл</a>
      </li>`;
  }

  function home() {
    document.title = `${BRAND} | Бага ангийн хичээл`;
    const h1 = [...BRAND].map((ch, i) =>
      `<span class="tw ${cls(ch)}" style="animation-delay:${i * 60}ms">${esc(ch)}</span>`).join("");
    const latest = LESSONS.slice().reverse().slice(0, 5);
    app.innerHTML = `
      <header class="hero">
        <h1 aria-label="${BRAND}">${h1}</h1>
        <p>Бага ангийн хүүхдэд зориулсан хичээлүүд</p>
      </header>
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
        <ol class="lesson-list">${latest.map((l) => lessonRow(l, true)).join("")}</ol>` : ""}`;
  }

  function gradeView(g) {
    document.title = `${g}-р анги | ${BRAND}`;
    const inGrade = LESSONS.filter((l) => l.grade === g);
    const keys = [...new Set([...SUBJECTS.map((s) => s[0]), ...inGrade.map((l) => l.subject)])]
      .filter((k) => inGrade.some((l) => l.subject === k));
    app.innerHTML = `
      <div class="lesson-head">
        <a class="btn ghost back" href="#/">← Нүүр</a>
        <h1>${g}-р анги</h1>
      </div>
      ${keys.map((k) => {
        const [, ico, name] = subjectOf(k);
        return `<section class="subject">
          <h2 class="subject-title"><span aria-hidden="true">${ico}</span> ${name}</h2>
          <ol class="lesson-list">${inGrade.filter((l) => l.subject === k).map((l) => lessonRow(l)).join("")}</ol>
        </section>`;
      }).join("")}
      <p class="soon">${keys.length ? "Бусад хичээлүүд удахгүй нэмэгдэнэ." : "Энэ ангийн хичээлүүд удахгүй нэмэгдэнэ."}</p>`;
  }

  // ------------------------------------------------ хичээл
  function lessonView(l, tab) {
    document.title = `${subjectName(l.subject)}, ${l.number}-р хичээл: ${[...l.letters].join(" ")} | ${BRAND}`;
    app.innerHTML = `
      <div class="lesson-head">
        <a class="btn ghost back" href="#/g/${l.grade}">← ${l.grade}-р анги</a>
        <h1>${l.number}-р хичээл <small>${l.grade}-р анги, ${subjectName(l.subject)}</small></h1>
        <div class="lesson-letters" aria-label="Үсгүүд">
          ${[...l.letters].map((ch) => `<span class="mini${l.new.includes(ch) ? " new" : ""}">${colorize(ch)}</span>`).join("")}
        </div>
      </div>
      <div class="tabs" role="tablist">
        ${TABS.map(([k, ico, lbl, col]) => `
          <button class="tab" role="tab" aria-selected="${k === tab}" data-tab="${k}" style="--tabc:${col}">
            <span class="ico" aria-hidden="true">${ico}</span><span class="lbl">${lbl}</span>
          </button>`).join("")}
      </div>
      <section class="panel" role="tabpanel"></section>`;
    $$(".tab").forEach((b) => b.addEventListener("click", () => { location.hash = `#/${l.id}/${b.dataset.tab}`; }));
    const panel = $(".panel");
    ({ video: videoPanel, letters: lettersPanel, syl: sylPanel, words: wordsPanel, sent: sentPanel, game: gamePanel })[tab](panel, l);
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
              ${c.emoji ? `<span class="em" aria-hidden="true">${c.emoji}</span>` : ""}<span>${colorize(c.example, c.ch)}</span>
            </button>` : ""}
          </div>`).join("")}
      </div>`;
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
    p.innerHTML = `<h2>Өгүүлбэр уншъя</h2>
      <p class="hint">▶ дээр дарвал үг үгээр нь, дараа нь бүтэн өгүүлбэрийг уншина.</p>
      ${l.sentences.map((s, i) => `
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
    let pool = l.game.length >= 3 ? l.game : l.syllables.flat().map((s) => ({ w: s.t, a: s.a }));
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

  route();
})();
