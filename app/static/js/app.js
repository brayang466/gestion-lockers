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

/**
 * Campos marcados con data-numeric-only: solo dígitos (texto) o entero con signo opcional (type="number").
 * Muestra un aviso encima del campo si se intenta introducir letras u otros caracteres no permitidos.
 */
(function () {
  "use strict";
  var MSG =
    "Este campo solo admite números. No use letras ni caracteres que no sean dígitos (0–9).";

  function showHint(el, show) {
    if (!el) return;
    if (show) {
      el.removeAttribute("hidden");
      clearTimeout(el._hideT);
      el._hideT = setTimeout(function () {
        el.setAttribute("hidden", "");
      }, 4500);
    } else {
      el.setAttribute("hidden", "");
    }
  }

  function ensureHint(input) {
    if (!input.id) {
      input.id = "inp-num-" + input.name + "-" + String(Math.random()).slice(2, 9);
    }
    var nid = "numeric-err-" + input.id;
    var el = document.getElementById(nid);
    if (!el) {
      el = document.createElement("div");
      el.id = nid;
      el.className = "field-numeric-error";
      el.setAttribute("role", "alert");
      el.setAttribute("hidden", "");
      el.textContent = MSG;
      input.parentNode.insertBefore(el, input);
    }
    return el;
  }

  function isDigitsOnly(s) {
    return s === "" || /^\d+$/.test(s);
  }

  /** type=number en la app: enteros sin signo (cantidades, conteos). */
  function isWholeNumberStr(s) {
    return s === "" || /^\d+$/.test(s);
  }

  function bindInput(input) {
    if (input.getAttribute("data-numeric-only") !== "1") return;
    if (input.readOnly || input.disabled) return;
    var hint = ensureHint(input);
    var isNumberType = input.type === "number";

    function onInput() {
      var v = input.value;
      var ok = isNumberType ? isWholeNumberStr(v) : isDigitsOnly(v);
      if (ok) {
        showHint(hint, false);
        return;
      }
      var cleaned = v.replace(/\D/g, "");
      if (input.value !== cleaned) {
        input.value = cleaned;
        showHint(hint, true);
      }
    }

    input.addEventListener("beforeinput", function (e) {
      if (e.data == null || e.data === "") return;
      var ok = isNumberType
        ? /^\d+$/.test(e.data)
        : /^\d+$/.test(e.data);
      if (!ok) {
        e.preventDefault();
        showHint(hint, true);
      }
    });

    input.addEventListener("paste", function (e) {
      var t = (e.clipboardData || window.clipboardData).getData("text") || "";
      var ok = isNumberType ? isWholeNumberStr(t.trim()) : isDigitsOnly(t.trim());
      if (!ok) {
        e.preventDefault();
        showHint(hint, true);
      }
    });

    input.addEventListener("input", onInput);
    input.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key.length === 1) {
        if (!/\d/.test(e.key)) {
          e.preventDefault();
          showHint(hint, true);
        }
      }
    });
  }

  function init(root) {
    (root || document).querySelectorAll("input[data-numeric-only='1']").forEach(bindInput);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
