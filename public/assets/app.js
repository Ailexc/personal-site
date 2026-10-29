(function () {
  "use strict";

  var STORAGE_LANG = "ailexc.lang";
  var STORAGE_THEME = "ailexc.theme";

  var html = document.documentElement;
  var langBtn = document.getElementById("langToggle");
  var themeBtn = document.getElementById("themeToggle");
  var qrBtn = document.getElementById("qrToggle");
  var qrPanel = document.getElementById("qrPanel");
  var header = document.querySelector(".site-header");
  var yearEl = document.getElementById("year");

  /* ---------- language ---------- */
  function detectLang() {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_LANG); } catch (e) {}
    if (saved === "zh" || saved === "en") return saved;
    var nav = (navigator.language || "zh").toLowerCase();
    return nav.indexOf("zh") === 0 ? "zh" : "en";
  }

  function applyLang(lang) {
    var dict = (window.I18N && window.I18N[lang]) || {};
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      var value = dict[key];
      if (typeof value === "string") el.innerHTML = value;
    });
    html.setAttribute("lang", lang === "zh" ? "zh-CN" : "en");
    if (langBtn) {
      langBtn.textContent = lang === "zh" ? "EN" : "中";
      langBtn.setAttribute("aria-label", lang === "zh" ? "Switch to English" : "切换到中文");
    }
    try { localStorage.setItem(STORAGE_LANG, lang); } catch (e) {}
  }

  var currentLang = detectLang();
  applyLang(currentLang);

  if (langBtn) {
    langBtn.addEventListener("click", function () {
      currentLang = currentLang === "zh" ? "en" : "zh";
      applyLang(currentLang);
    });
  }

  /* ---------- theme ---------- */
  function detectTheme() {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_THEME); } catch (e) {}
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    html.setAttribute("data-theme", theme);
    if (themeBtn) {
      themeBtn.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    }
    try { localStorage.setItem(STORAGE_THEME, theme); } catch (e) {}
  }

  var currentTheme = detectTheme();
  applyTheme(currentTheme);

  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      currentTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(currentTheme);
    });
  }

  /* ---------- QR code ---------- */
  if (qrBtn && qrPanel) {
    qrBtn.addEventListener("click", function () {
      var open = qrPanel.hasAttribute("hidden");
      if (open) {
        qrPanel.removeAttribute("hidden");
      } else {
        qrPanel.setAttribute("hidden", "");
      }
      qrBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  /* ---------- header shadow on scroll ---------- */
  function onScroll() {
    if (!header) return;
    if (window.scrollY > 8) header.classList.add("scrolled");
    else header.classList.remove("scrolled");
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---------- year ---------- */
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());
})();
