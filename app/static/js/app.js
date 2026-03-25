/**
 * LockerBeef app shell — tema claro/oscuro (misma clave que login)
 */
(function () {
  "use strict";
  var KEY = "lockerbeef-login-theme";

  function setMeta(theme) {
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", theme === "dark" ? "#050b14" : "#e8eef7");
  }

  function init() {
    var stored = localStorage.getItem(KEY);
    var prefersLight =
      window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    var theme = stored || (prefersLight ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
    setMeta(theme);
    var btn = document.getElementById("appThemeToggle");
    if (btn) {
      btn.setAttribute(
        "aria-label",
        theme === "dark" ? "Activar modo claro" : "Activar modo oscuro"
      );
      btn.setAttribute("title", theme === "dark" ? "Modo claro" : "Modo oscuro");
    }
  }

  function toggle() {
    var cur = document.documentElement.getAttribute("data-theme") || "dark";
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(KEY, next);
    setMeta(next);
    var btn = document.getElementById("appThemeToggle");
    if (btn) {
      btn.setAttribute(
        "aria-label",
        next === "dark" ? "Activar modo claro" : "Activar modo oscuro"
      );
      btn.setAttribute("title", next === "dark" ? "Modo claro" : "Modo oscuro");
    }
  }

  function bindToggle() {
    var btn = document.getElementById("appThemeToggle");
    if (btn) {
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        toggle();
      });
    }
  }

  function boot() {
    init();
    bindToggle();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
