/* 访问统计前端渲染（数据由 scripts/collect-visits.py 每 10 分钟生成 visits.json）
   - 热力图每格可点击：点某天 → 第三格显示那天的访问量；再点一次回到「今日」
   - 下方项目点击：分段堆叠条（预览 / 介绍页 / 仓库），按访客去重 */
(function () {
  "use strict";

  var ENDPOINT = "/visits.json";
  var RAMP = ["l0", "l1", "l2", "l3", "l4"];
  var KIND_ORDER = ["live", "intro", "repo"];
  var KIND_CLASS = { live: "seg-live", intro: "seg-intro", repo: "seg-repo" };
  var KIND_LABEL_KEY = { live: "clicks.preview", intro: "clicks.intro", repo: "clicks.repo" };

  var dataCache = null;
  var selectedDate = null;   // null = 默认（今日）

  function currentLang() {
    return document.documentElement.lang === "en" ? "en" : "zh";
  }

  function t(key, fallback, vars) {
    var dict = (window.I18N && window.I18N[currentLang()]) || {};
    var s = dict[key] || fallback || key;
    if (vars) {
      for (var k in vars) {
        if (Object.prototype.hasOwnProperty.call(vars, k)) {
          s = s.replace("{" + k + "}", vars[k]);
        }
      }
    }
    return s;
  }

  function level(pv, max) {
    if (!pv || pv <= 0) return 0;
    if (max <= 1) return 2;
    var r = pv / max;
    if (r <= 0.25) return 1;
    if (r <= 0.5) return 2;
    if (r <= 0.75) return 3;
    return 4;
  }

  /* 数字滚动：从 0 递增到目标值。
     注意：requestAnimationFrame 在后台标签页会被浏览器暂停/节流，
     因此用 setTimeout 计时 + rAF 绘制，并加一道兜底保证最终值一定正确。
     每个元素自带序号：连续调用（快速点多个日期）时旧的动画自动作废。 */
  function countUp(el, to, duration) {
    if (!el) return;
    var seq = (el.__seq || 0) + 1;
    el.__seq = seq;

    var target = Number(to) || 0;
    if (target === 0) { el.textContent = "0"; return; }

    var dur = duration || 900;
    var t0 = Date.now();
    var done = false;

    function alive() { return el.__seq === seq; }

    function paint() {
      if (done || !alive()) return;
      var p = Math.min((Date.now() - t0) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);   // easeOutCubic
      el.textContent = Math.round(target * eased).toLocaleString();
      if (p < 1) {
        requestAnimationFrame(paint);
        setTimeout(paint, 32);              // rAF 被节流时的备用推进
      }
    }

    function finalize() {
      if (done || !alive()) return;
      done = true;
      el.textContent = target.toLocaleString();
    }

    paint();
    setTimeout(finalize, dur + 120);        // 兜底：无论动画是否执行，最终值都对
  }

  function fmtDate(iso) {
    // "2026-10-31" → "10-31"
    var p = iso.split("-");
    return p.length === 3 ? p[1] + "-" + p[2] : iso;
  }

  /* ---------- 第三格：今日 ↔ 所选日期 ---------- */

  function todayOf(days) {
    return days.length ? days[days.length - 1].date : "";
  }

  function updateThirdKpi() {
    var days = (dataCache && dataCache.days) || [];
    var strong = document.querySelector('[data-kpi="today_pv"]');
    var label = document.getElementById("kpiDateLabel");
    if (!strong || !label) return;

    var today = todayOf(days);
    var target = selectedDate || today;
    var pv = 0;
    for (var i = 0; i < days.length; i++) {
      if (days[i].date === target) { pv = days[i].pv; break; }
    }

    countUp(strong, pv);

    if (selectedDate && selectedDate !== today) {
      label.textContent = fmtDate(selectedDate);
      label.removeAttribute("data-i18n");
    } else {
      label.setAttribute("data-i18n", "visits.today");
      label.textContent = t("visits.today", "今日");
    }
  }

  function updateCellStates() {
    var cal = document.getElementById("visitCal");
    if (!cal) return;
    var cells = cal.querySelectorAll(".vcal-cell");
    for (var i = 0; i < cells.length; i++) {
      var on = selectedDate && cells[i].getAttribute("data-date") === selectedDate;
      cells[i].classList.toggle("is-active", !!on);
      cells[i].setAttribute("aria-pressed", on ? "true" : "false");
    }
  }

  function onCellClick(date) {
    var days = (dataCache && dataCache.days) || [];
    var today = todayOf(days);

    if (date === today || date === selectedDate) {
      selectedDate = null;          // 点今天，或再点一次已选中的那天 → 回到今日
    } else {
      selectedDate = date;
    }
    updateThirdKpi();
    updateCellStates();
  }

  /* ---------- 热力图 ---------- */

  function renderCalendar(data) {
    var cal = document.getElementById("visitCal");
    var days = data.days || [];
    if (!cal || !days.length) return;

    cal.setAttribute("aria-label", t("visits.calLabel", "最近 30 天访问量，可点选日期查看"));

    var maxPv = 0;
    for (var i = 0; i < days.length; i++) {
      if (days[i].pv > maxPv) maxPv = days[i].pv;
    }

    var frag = document.createDocumentFragment();
    for (var j = 0; j < days.length; j++) {
      var d = days[j];
      var cell = document.createElement("button");
      cell.type = "button";
      cell.className = "vcal-cell " + RAMP[level(d.pv, maxPv)];
      cell.setAttribute("data-date", d.date);
      cell.setAttribute("aria-pressed", "false");
      var tip = t("visits.cellTip", "{d} · {pv} 次浏览 / {uv} 位访客",
        { d: d.date, pv: d.pv, uv: d.uv });
      cell.setAttribute("aria-label", tip);
      cell.setAttribute("title", tip);
      cell.style.animationDelay = (j * 12) + "ms";
      frag.appendChild(cell);
    }
    cal.textContent = "";
    cal.appendChild(frag);

    // 事件委托：30 个格子只挂一个监听
    if (!cal.__bound) {
      cal.__bound = true;
      cal.addEventListener("click", function (e) {
        var el = e.target && e.target.closest ? e.target.closest(".vcal-cell") : null;
        if (el) onCellClick(el.getAttribute("data-date"));
      });
    }

    var s = document.getElementById("calStart");
    var e2 = document.getElementById("calEnd");
    if (s) s.textContent = fmtDate(days[0].date);
    if (e2) e2.textContent = fmtDate(days[days.length - 1].date);
  }

  /* ---------- 项目点击（分段堆叠条） ---------- */

  function renderClicks(clicks) {
    var block = document.getElementById("clickBlock");
    var list = document.getElementById("clickList");
    var totalEl = document.getElementById("clickTotal");
    var foot = block ? block.querySelector(".click-foot") : null;
    if (!block || !list) return;

    block.hidden = false;
    list.textContent = "";

    var projects = (clicks && clicks.projects) || [];
    var totalPv = (clicks && clicks.total_pv) || 0;

    // 零状态：还没有任何点击，给一句说明而不是留空白
    if (!totalPv || !projects.length) {
      var empty = document.createElement("li");
      empty.className = "click-empty";
      empty.style.listStyle = "none";
      empty.textContent = t("clicks.empty", "还没有点击数据 · 从主页点开项目后开始累计");
      list.appendChild(empty);
      if (totalEl) totalEl.textContent = "";
      if (foot) foot.hidden = true;
      return;
    }

    if (foot) foot.hidden = false;

    if (totalEl) {
      totalEl.textContent = t("clicks.total", "共 {pv} 次 · {uv} 人", {
        pv: totalPv.toLocaleString(),
        uv: ((clicks && clicks.total_uv) || 0).toLocaleString()
      });
    }

    // UV 不可相加：一人点了两个类别，会在两个类别里各计 1 人。
    // 所以条形内部统一用「三类 UV 之和」作分母，段宽才能自洽到 100%。
    function kindSum(p) {
      var k = p.kinds || {};
      var n = 0;
      KIND_ORDER.forEach(function (kind) { n += (k[kind] || {}).uv || 0; });
      return n;
    }

    var maxSum = 1;
    for (var i = 0; i < projects.length; i++) {
      var sm = kindSum(projects[i]);
      if (sm > maxSum) maxSum = sm;
    }

    var frag = document.createDocumentFragment();
    projects.forEach(function (p) {
      var li = document.createElement("li");
      li.className = "click-row";

      var k = p.kinds || {};
      li.title = t("clicks.detail", "{uv} 人 · 共 {pv} 次", {
        uv: p.uv || 0,
        pv: p.pv || 0,
        live: (k.live || {}).uv || 0,
        intro: (k.intro || {}).uv || 0,
        repo: (k.repo || {}).uv || 0
      });

      var nameEl = document.createElement("span");
      nameEl.className = "click-name";
      nameEl.textContent = t("clicks.p." + p.key, p.key);

      var sum = kindSum(p);
      var bar = document.createElement("span");
      bar.className = "click-bar";
      bar.style.width = Math.max(6, Math.round((sum / maxSum) * 100)) + "%";

      KIND_ORDER.forEach(function (kind) {
        var kk = k[kind] || { pv: 0, uv: 0 };
        if (!kk.uv) return;

        var seg = document.createElement("i");
        seg.className = "seg " + KIND_CLASS[kind];
        var pct = sum > 0 ? (kk.uv / sum) * 100 : 0;
        seg.style.width = pct.toFixed(2) + "%";
        // 太窄的段放不下数字，只留颜色（明细在 title 里）
        if (pct >= 8) seg.textContent = kk.uv;
        seg.setAttribute("title", t(KIND_LABEL_KEY[kind], kind) + " · "
          + t("clicks.people", "{n} 人", { n: kk.uv }));
        bar.appendChild(seg);
      });

      var sumEl = document.createElement("span");
      sumEl.className = "click-sum";
      sumEl.textContent = p.uv || 0;

      li.appendChild(nameEl);
      li.appendChild(bar);
      li.appendChild(sumEl);
      frag.appendChild(li);
    });

    list.appendChild(frag);
  }

  /* ---------- 主渲染 ---------- */

  function render(data) {
    dataCache = data;

    // ── 数字
    countUp(document.querySelector('[data-kpi="total_pv"]'), data.total_pv);
    countUp(document.querySelector('[data-kpi="total_uv"]'), data.total_uv);

    renderCalendar(data);
    updateThirdKpi();
    updateCellStates();
    renderClicks(data.clicks);

    // ── 说明
    var note = document.getElementById("visitNote");
    if (note) {
      var days = data.days || [];
      var since = data.since || (days.length ? days[0].date : "");
      note.textContent = t("visits.note", "自 {since} 起统计 · 每 10 分钟更新", {
        since: since
      });
    }
  }

  function fail() {
    // 数据不可用时不显示板块，避免空白占位
    var sec = document.getElementById("visits");
    if (sec) sec.hidden = true;
  }

  function boot() {
    if (!document.getElementById("visits")) return;

    // 切换语言后重刷动态文案（app.js 的 applyLang 会先把静态文案改掉）
    var langBtn = document.getElementById("langToggle");
    if (langBtn) {
      langBtn.addEventListener("click", function () {
        setTimeout(function () { if (dataCache) render(dataCache); }, 0);
      });
    }

    var req = new Request(ENDPOINT, { cache: "no-store" });
    fetch(req, { headers: { Accept: "application/json" } })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(render)
      .catch(fail);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
