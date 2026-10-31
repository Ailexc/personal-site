/* 访问统计前端渲染（数据由 scripts/collect-visits.py 每 10 分钟生成 visits.json） */
(function () {
  "use strict";

  var ENDPOINT = "/visits.json";
  var RAMP = ["l0", "l1", "l2", "l3", "l4"];

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
     因此用 setTimeout 计时 + rAF 绘制，并加一道兜底保证最终值一定正确。 */
  function countUp(el, to, duration) {
    if (!el) return;
    var target = Number(to) || 0;
    if (target === 0) { el.textContent = "0"; return; }

    var dur = duration || 900;
    var t0 = Date.now();
    var done = false;

    function paint() {
      if (done) return;
      var p = Math.min((Date.now() - t0) / dur, 1);
      var eased = 1 - Math.pow(1 - p, 3);   // easeOutCubic
      el.textContent = Math.round(target * eased).toLocaleString();
      if (p < 1) {
        requestAnimationFrame(paint);
        setTimeout(paint, 32);              // rAF 被节流时的备用推进
      }
    }

    function finalize() {
      if (done) return;
      done = true;
      el.textContent = target.toLocaleString();
    }

    paint();
    setTimeout(finalize, dur + 120);        // 兜底：无论动画是否执行，最终值都对
  }

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  function fmtDate(iso) {
    // "2026-10-31" → "10-31"
    var p = iso.split("-");
    return p.length === 3 ? p[1] + "-" + p[2] : iso;
  }

  function render(data) {
    // ── 数字
    countUp(document.querySelector('[data-kpi="total_pv"]'), data.total_pv);
    countUp(document.querySelector('[data-kpi="total_uv"]'), data.total_uv);
    countUp(document.querySelector('[data-kpi="today_pv"]'), data.today_pv);

    // ── 日历热力图
    var cal = document.getElementById("visitCal");
    var days = data.days || [];
    if (cal && days.length) {
      var maxPv = 0;
      for (var i = 0; i < days.length; i++) {
        if (days[i].pv > maxPv) maxPv = days[i].pv;
      }
      var frag = document.createDocumentFragment();
      for (var j = 0; j < days.length; j++) {
        var d = days[j];
        var cell = document.createElement("i");
        cell.className = "vcal-cell " + RAMP[level(d.pv, maxPv)];
        cell.setAttribute("title", d.date + " · " + d.pv + " 次浏览 / " + d.uv + " 位访客");
        // 逐格渐入，制造扫描感
        cell.style.animationDelay = (j * 12) + "ms";
        frag.appendChild(cell);
      }
      cal.textContent = "";
      cal.appendChild(frag);
    }

    // ── 起止标签
    if (days.length) {
      var s = document.getElementById("calStart");
      var e = document.getElementById("calEnd");
      if (s) s.textContent = fmtDate(days[0].date);
      if (e) e.textContent = fmtDate(days[days.length - 1].date);
    }

    // ── 说明
    var note = document.getElementById("visitNote");
    if (note) {
      var since = data.since || (days.length ? days[0].date : "");
      var tpl = (window.I18N && window.I18N.visits && window.I18N.visits.note) ||
                "自 {since} 起统计 · 每 10 分钟更新";
      note.textContent = tpl.replace("{since}", since);
    }
  }

  function fail() {
    // 数据不可用时不显示板块，避免空白占位
    var sec = document.getElementById("visits");
    if (sec) sec.hidden = true;
  }

  function boot() {
    if (!document.getElementById("visits")) return;
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
