/**
 * Calendario de recordatorios en el dashboard (localStorage + notificaciones).
 */
(function () {
  "use strict";

  var mount = document.getElementById("reminderCalendarMount");
  if (!mount) return;

  var userId = mount.getAttribute("data-user-id") || "0";
  var STORAGE = "lockerbeef-reminders-v1-" + userId;
  var FIRED = "lockerbeef-reminders-fired-" + userId;

  var state = {
    viewYear: new Date().getFullYear(),
    viewMonth: new Date().getMonth(),
    selectedDate: null,
  };

  var monthNames = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
  ];
  var dayLabels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function toYMD(y, m, d) {
    return y + "-" + pad(m + 1) + "-" + pad(d);
  }

  function parseYMD(s) {
    var p = (s || "").split("-");
    if (p.length !== 3) return null;
    return { y: +p[0], m: +p[1] - 1, d: +p[2] };
  }

  function loadReminders() {
    try {
      var raw = localStorage.getItem(STORAGE);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      return [];
    }
  }

  function saveReminders(list) {
    localStorage.setItem(STORAGE, JSON.stringify(list));
  }

  function uid() {
    return "r-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
  }

  function remindersForDate(ymd) {
    return loadReminders().filter(function (r) {
      return r.date === ymd;
    });
  }

  function countForMonth(y, m) {
    var list = loadReminders();
    var c = 0;
    list.forEach(function (r) {
      var p = parseYMD(r.date);
      if (p && p.y === y && p.m === m) c++;
    });
    return c;
  }

  function getFiredMap() {
    try {
      return JSON.parse(localStorage.getItem(FIRED) || "{}");
    } catch (e) {
      return {};
    }
  }

  function setFiredMap(map) {
    localStorage.setItem(FIRED, JSON.stringify(map));
  }

  function toast(msg) {
    var t = document.getElementById("reminderToast");
    if (!t) return;
    t.textContent = msg;
    t.hidden = false;
    t.setAttribute("aria-live", "polite");
    clearTimeout(toast._h);
    toast._h = setTimeout(function () {
      t.hidden = true;
    }, 5000);
  }

  function checkDueReminders() {
    var now = new Date();
    var list = loadReminders();
    var fired = getFiredMap();
    var changed = false;
    list.forEach(function (r) {
      var time = (r.time && r.time.trim()) || "09:00";
      var parts = time.split(":");
      var hh = parseInt(parts[0], 10) || 9;
      var mm = parseInt(parts[1], 10) || 0;
      var p = parseYMD(r.date);
      if (!p) return;
      var due = new Date(p.y, p.m, p.d, hh, mm, 0, 0);
      var diff = now - due;
      if (diff >= 0 && diff < 120000) {
        var key = r.id + "_" + r.date + "_" + time;
        if (!fired[key]) {
          fired[key] = now.toISOString();
          changed = true;
          toast("Recordatorio: " + (r.title || ""));
        }
      }
    });
    if (changed) setFiredMap(fired);
  }

  function buildCalendarGrid() {
    var y = state.viewYear;
    var m = state.viewMonth;
    var first = new Date(y, m, 1);
    var startDow = first.getDay();
    var mondayBased = startDow === 0 ? 6 : startDow - 1;
    var lastDay = new Date(y, m + 1, 0).getDate();
    var today = new Date();
    var isTodayYM = today.getFullYear() === y && today.getMonth() === m;

    var cells = [];
    var i;
    for (i = 0; i < mondayBased; i++) {
      cells.push({ type: "pad" });
    }
    for (var d = 1; d <= lastDay; d++) {
      var ymd = toYMD(y, m, d);
      var n = remindersForDate(ymd).length;
      var isToday = isTodayYM && today.getDate() === d;
      cells.push({ type: "day", d: d, ymd: ymd, n: n, isToday: isToday });
    }
    return cells;
  }

  function render() {
    var y = state.viewYear;
    var m = state.viewMonth;
    var titleEl = document.getElementById("calMonthTitle");
    if (titleEl) titleEl.textContent = monthNames[m] + " " + y;

    var grid = document.getElementById("calGrid");
    if (!grid) return;
    grid.innerHTML = "";

    dayLabels.forEach(function (lbl) {
      var th = document.createElement("div");
      th.className = "cal-weekday";
      th.textContent = lbl;
      grid.appendChild(th);
    });

    var cells = buildCalendarGrid();
    cells.forEach(function (c) {
      var el = document.createElement("button");
      el.type = "button";
      el.className = "cal-cell";
      if (c.type === "pad") {
        el.className += " cal-cell--pad";
        el.disabled = true;
        el.setAttribute("aria-hidden", "true");
      } else {
        el.className += " cal-cell--day";
        el.textContent = String(c.d);
        el.setAttribute("data-date", c.ymd);
        el.setAttribute("aria-label", "Día " + c.d + ", " + c.n + " recordatorios");
        if (c.isToday) {
          el.className += " cal-cell--today";
          el.setAttribute("aria-current", "date");
        }
        if (c.n > 0) el.className += " cal-cell--has";
        el.addEventListener("click", function () {
          openDayPanel(c.ymd);
        });
      }
      grid.appendChild(el);
    });

    var badge = document.getElementById("calMonthBadge");
    if (badge) {
      var total = countForMonth(y, m);
      badge.textContent = total ? String(total) : "";
      badge.hidden = !total;
    }
  }

  function openDayPanel(ymd) {
    state.selectedDate = ymd;
    var panel = document.getElementById("calDayPanel");
    var title = document.getElementById("calDayTitle");
    var list = document.getElementById("calDayList");
    if (!panel || !title || !list) return;

    var p = parseYMD(ymd);
    title.textContent = p
      ? p.d + " de " + monthNames[p.m] + " " + p.y
      : ymd;

    list.innerHTML = "";
    var items = remindersForDate(ymd);
    if (!items.length) {
      var empty = document.createElement("p");
      empty.className = "cal-day-empty";
      empty.textContent = "Sin recordatorios. Añade uno abajo.";
      list.appendChild(empty);
    } else {
      items.forEach(function (r) {
        var row = document.createElement("div");
        row.className = "cal-day-item";
        var meta = document.createElement("span");
        meta.className = "cal-day-item-meta";
        meta.textContent = (r.time || "09:00") + " — ";
        var tit = document.createElement("strong");
        tit.textContent = r.title || "(sin título)";
        row.appendChild(meta);
        row.appendChild(tit);
        var del = document.createElement("button");
        del.type = "button";
        del.className = "cal-day-del";
        del.setAttribute("aria-label", "Eliminar recordatorio");
        del.textContent = "×";
        del.addEventListener("click", function () {
          var all = loadReminders().filter(function (x) {
            return x.id !== r.id;
          });
          saveReminders(all);
          openDayPanel(ymd);
          render();
        });
        row.appendChild(del);
        list.appendChild(row);
      });
    }

    document.getElementById("calFormDate").value = ymd;
    panel.hidden = false;
  }

  function closeDayPanel() {
    var panel = document.getElementById("calDayPanel");
    if (panel) panel.hidden = true;
    state.selectedDate = null;
  }

  function bindControls() {
    document.getElementById("calPrev")?.addEventListener("click", function () {
      state.viewMonth--;
      if (state.viewMonth < 0) {
        state.viewMonth = 11;
        state.viewYear--;
      }
      render();
    });
    document.getElementById("calNext")?.addEventListener("click", function () {
      state.viewMonth++;
      if (state.viewMonth > 11) {
        state.viewMonth = 0;
        state.viewYear++;
      }
      render();
    });
    document.getElementById("calTodayBtn")?.addEventListener("click", function () {
      var n = new Date();
      state.viewYear = n.getFullYear();
      state.viewMonth = n.getMonth();
      render();
      openDayPanel(toYMD(n.getFullYear(), n.getMonth(), n.getDate()));
    });

    document.getElementById("calDayClose")?.addEventListener("click", closeDayPanel);
    document.getElementById("calForm")?.addEventListener("submit", function (e) {
      e.preventDefault();
      var title = (document.getElementById("calFormTitle")?.value || "").trim();
      if (!title) return;
      var date = document.getElementById("calFormDate")?.value;
      var time = (document.getElementById("calFormTime")?.value || "09:00").trim();
      var all = loadReminders();
      all.push({ id: uid(), date: date, time: time, title: title });
      saveReminders(all);
      document.getElementById("calFormTitle").value = "";
      openDayPanel(date);
      render();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeDayPanel();
    });
  }

  mount.innerHTML =
    '<div class="reminder-cal">' +
    '<div class="reminder-cal-toolbar">' +
    '<button type="button" class="cal-nav-btn" id="calPrev" aria-label="Mes anterior">‹</button>' +
    '<h4 class="cal-month-title" id="calMonthTitle"></h4>' +
    '<span class="cal-month-badge" id="calMonthBadge" hidden></span>' +
    '<button type="button" class="cal-nav-btn" id="calNext" aria-label="Mes siguiente">›</button>' +
    '<button type="button" class="cal-today-btn" id="calTodayBtn">Hoy</button>' +
    "</div>" +
    '<div class="cal-grid" id="calGrid" role="grid" aria-label="Calendario de recordatorios"></div>' +
    '<div class="cal-day-panel" id="calDayPanel" hidden>' +
    '<div class="cal-day-panel-head">' +
    '<h4 id="calDayTitle"></h4>' +
    '<button type="button" class="cal-day-close" id="calDayClose" aria-label="Cerrar">×</button>' +
    "</div>" +
    '<div id="calDayList" class="cal-day-list"></div>' +
    '<form class="cal-day-form" id="calForm">' +
    '<input type="hidden" id="calFormDate" />' +
    '<label class="cal-label"><span>Título</span><input type="text" id="calFormTitle" required maxlength="200" placeholder="Ej. Revisar inventario" /></label>' +
    '<label class="cal-label"><span>Hora del aviso</span><input type="time" id="calFormTime" value="09:00" /></label>' +
    '<button type="submit" class="cal-submit-btn">Guardar recordatorio</button>' +
    "</form>" +
    "</div>" +
    "</div>";

  bindControls();
  render();
  checkDueReminders();
  setInterval(checkDueReminders, 30000);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") checkDueReminders();
  });
})();

