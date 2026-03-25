/**
 * LockerBeef login — vistas, validación, tema, toggles contraseña
 */
(function () {
  "use strict";

  var THEME_KEY = "lockerbeef-login-theme";

  function initTheme() {
    var stored = localStorage.getItem(THEME_KEY);
    var prefersLight =
      window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
    var theme = stored || (prefersLight ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", theme);
    updateThemeToggleLabel(theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#050b14" : "#e8eef7");
  }

  function updateThemeToggleLabel(theme) {
    var btn = document.getElementById("themeToggle");
    if (!btn) return;
    btn.setAttribute(
      "aria-label",
      theme === "dark" ? "Activar modo claro" : "Activar modo oscuro"
    );
    btn.setAttribute("title", theme === "dark" ? "Modo claro" : "Modo oscuro");
  }

  function toggleTheme() {
    var cur = document.documentElement.getAttribute("data-theme") || "dark";
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    updateThemeToggleLabel(next);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", next === "dark" ? "#050b14" : "#e8eef7");
  }

  var viewLogin = document.getElementById("viewLogin");
  var viewRecover = document.getElementById("viewRecover");
  var viewRegister = document.getElementById("viewRegister");
  var showRecover = document.getElementById("showRecover");
  var showLogin = document.getElementById("showLogin");
  var showRegister = document.getElementById("showRegister");
  var showLoginFromRegister = document.getElementById("showLoginFromRegister");
  var themeToggle = document.getElementById("themeToggle");

  initTheme();
  if (themeToggle) {
    themeToggle.addEventListener("click", toggleTheme);
  }

  function goToRecover() {
    if (!viewLogin || !viewRecover) return;
    viewLogin.classList.add("hidden");
    viewLogin.classList.remove("active", "login-appear");
    if (viewRegister) {
      viewRegister.classList.add("hidden");
      viewRegister.classList.remove("active", "register-enter");
    }
    viewRecover.classList.remove("hidden");
    viewRecover.classList.add("active", "recover-enter");
    var re = document.getElementById("recoverEmail");
    if (re) re.focus();
  }

  function goToRegister() {
    if (!viewLogin || !viewRegister || !viewRecover) return;
    viewLogin.classList.add("hidden");
    viewLogin.classList.remove("active", "login-appear");
    viewRecover.classList.add("hidden");
    viewRecover.classList.remove("active", "recover-enter");
    viewRegister.classList.remove("hidden");
    viewRegister.classList.add("active", "register-enter");
    var first = document.getElementById("regNombre");
    if (first) first.focus();
  }

  function goToLogin() {
    if (!viewLogin || !viewRecover) return;
    viewRecover.classList.add("hidden");
    viewRecover.classList.remove("active", "recover-enter");
    if (viewRegister) {
      viewRegister.classList.add("hidden");
      viewRegister.classList.remove("active", "register-enter");
    }
    viewLogin.classList.remove("hidden");
    viewLogin.classList.remove("login-appear");
    viewLogin.classList.add("active");
    var flashContainer = document.getElementById("loginFlashContainer");
    if (flashContainer) {
      flashContainer.style.display = "none";
      flashContainer.innerHTML = "";
    }
    requestAnimationFrame(function () {
      viewLogin.classList.add("login-appear");
    });
    var email = document.getElementById("email");
    if (email) email.focus();
  }

  if (showRecover)
    showRecover.addEventListener("click", function (e) {
      e.preventDefault();
      goToRecover();
    });
  if (showLogin)
    showLogin.addEventListener("click", function (e) {
      e.preventDefault();
      goToLogin();
    });
  if (showRegister)
    showRegister.addEventListener("click", function (e) {
      e.preventDefault();
      goToRegister();
    });
  if (showLoginFromRegister)
    showLoginFromRegister.addEventListener("click", function (e) {
      e.preventDefault();
      goToLogin();
    });

  if (document.body.getAttribute("data-show-register") === "1" && viewRegister) {
    goToRegister();
  }

  function bindToggle(toggleId, inputId) {
    var toggle = document.getElementById(toggleId);
    var input = document.getElementById(inputId);
    if (!toggle || !input) return;
    toggle.addEventListener("click", function () {
      var isPass = input.type === "password";
      input.type = isPass ? "text" : "password";
      toggle.setAttribute("aria-pressed", isPass ? "true" : "false");
      toggle.setAttribute("title", isPass ? "Ocultar contraseña" : "Mostrar contraseña");
    });
  }

  bindToggle("togglePassword", "password");
  bindToggle("toggleRegPassword", "regPassword");
  bindToggle("toggleRegPassword2", "regPassword2");

  function validateField(input, errorEl, forceShow) {
    if (!input) return;
    var valid = input.checkValidity();
    var showError = !valid && (forceShow || input.value.length > 0);
    input.classList.toggle("is-invalid", showError);
    input.classList.toggle("is-valid", valid && input.value.length > 0);
    if (errorEl) errorEl.style.display = showError ? "block" : "none";
    var field = input.closest(".login-field");
    if (field) field.classList.toggle("has-error", showError);
  }

  var loginForm = document.getElementById("loginForm");
  if (loginForm) {
    ["email", "password"].forEach(function (id) {
      var input = document.getElementById(id);
      var fieldId = "field" + id.charAt(0).toUpperCase() + id.slice(1);
      var field = document.getElementById(fieldId);
      var errorEl = field && field.querySelector(".login-field-error");
      if (input) {
        input.addEventListener("blur", function () {
          validateField(input, errorEl);
        });
        input.addEventListener("input", function () {
          validateField(input, errorEl);
        });
      }
    });
    loginForm.addEventListener(
      "submit",
      function (e) {
        if (!loginForm.checkValidity()) {
          e.preventDefault();
          document.querySelectorAll("#fieldEmail, #fieldPassword").forEach(function (f) {
            var i = f.querySelector(".login-input");
            var err = f.querySelector(".login-field-error");
            if (i) validateField(i, err, true);
          });
        } else {
          var btn = document.getElementById("loginSubmit");
          if (btn) {
            btn.disabled = true;
            var txt = btn.querySelector(".btn-text");
            var sp = btn.querySelector(".spinner");
            if (txt) txt.style.display = "none";
            if (sp) sp.style.display = "block";
          }
        }
        loginForm.classList.add("was-validated");
      },
      false
    );
  }

  var recoverForm = document.getElementById("recoverForm");
  if (recoverForm) {
    var recoverEmail = document.getElementById("recoverEmail");
    var fieldRecover = document.getElementById("fieldRecoverEmail");
    var recoverError = fieldRecover && fieldRecover.querySelector(".login-field-error");
    if (recoverEmail) {
      recoverEmail.addEventListener("blur", function () {
        validateField(recoverEmail, recoverError);
      });
      recoverEmail.addEventListener("input", function () {
        validateField(recoverEmail, recoverError);
      });
    }
    recoverForm.addEventListener(
      "submit",
      function (e) {
        if (!recoverForm.checkValidity()) {
          e.preventDefault();
          validateField(recoverEmail, recoverError, true);
        } else {
          var btn = document.getElementById("recoverSubmit");
          if (btn) {
            btn.disabled = true;
            var txt = btn.querySelector(".btn-text");
            var sp = btn.querySelector(".spinner");
            if (txt) txt.style.display = "none";
            if (sp) sp.style.display = "block";
          }
        }
        recoverForm.classList.add("was-validated");
      },
      false
    );
  }

  var formRegistro = document.getElementById("formRegistro");
  var regPass = document.getElementById("regPassword");
  var regPass2 = document.getElementById("regPassword2");
  var regPasswordError = document.getElementById("regPasswordError");

  if (formRegistro && regPass && regPass2) {
    function validateRegPasswordStrength() {
      var p = regPass.value;
      if (!p.length) {
        regPass.setCustomValidity("");
        if (regPasswordError) regPasswordError.style.display = "none";
        var f0 = regPass.closest(".login-field");
        if (f0) f0.classList.remove("has-error");
        return true;
      }
      var hasUpper = /[A-Z]/.test(p);
      var hasNumber = /\d/.test(p);
      var hasSymbol = /[^A-Za-z0-9]/.test(p);
      var valid = p.length >= 8 && hasUpper && hasNumber && hasSymbol;
      var msg = valid ? "" : "Use 8 caracteres como mínimo, una mayúscula, un número y un símbolo.";
      regPass.setCustomValidity(msg);
      var field = regPass.closest(".login-field");
      if (field) field.classList.toggle("has-error", !valid);
      if (regPasswordError) regPasswordError.style.display = valid ? "none" : "block";
      return valid;
    }

    function checkRegPassMatch() {
      var match = !regPass2.value || regPass.value === regPass2.value;
      regPass2.setCustomValidity(match ? "" : "Las contraseñas no coinciden");
      var err = document.getElementById("regPassword2Error");
      var field = regPass2.closest(".login-field");
      if (field) {
        field.classList.toggle("has-error", !match && regPass2.value.length > 0);
        if (err) err.style.display = !match && regPass2.value.length > 0 ? "block" : "none";
      }
    }

    regPass.addEventListener("input", function () {
      validateRegPasswordStrength();
      checkRegPassMatch();
    });
    regPass2.addEventListener("input", checkRegPassMatch);
    formRegistro.addEventListener(
      "submit",
      function (e) {
        validateRegPasswordStrength();
        checkRegPassMatch();
        if (!formRegistro.checkValidity()) {
          e.preventDefault();
          validateRegPasswordStrength();
          formRegistro.querySelectorAll(".login-field").forEach(function (f) {
            var i = f.querySelector(".login-input");
            var err = f.querySelector(".login-field-error");
            if (i) validateField(i, err, true);
          });
        } else {
          var btn = document.getElementById("registerSubmit");
          if (btn) {
            btn.disabled = true;
            var txt = btn.querySelector(".btn-text");
            var sp = btn.querySelector(".spinner");
            if (txt) txt.style.display = "none";
            if (sp) sp.style.display = "block";
          }
        }
        formRegistro.classList.add("was-validated");
      },
      false
    );
  }
})();
