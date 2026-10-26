/* Job Finder frontend. Plain JS, no build step; talks to the FastAPI /api endpoints on the same origin. */
(() => {
  "use strict";

  // ============================================================
  // Small helpers
  // ============================================================
  const $ = (sel, root = document) => root.querySelector(sel);

  /** Build an element: h("div", { class: "x", onclick }, child, "text", ...). Strings are always text, never HTML. */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
        else if (k === "class") el.className = v;
        else if (k === "html") el.innerHTML = v; // only ever passed sanitized markdown
        else if (v === true) el.setAttribute(k, "");
        else el.setAttribute(k, v);
      }
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  const icon = (name, cls = "") => h("span", { class: `ms ${cls}`.trim(), "aria-hidden": "true" }, name);
  /** The Job Finder mark, "the seeker": a J with a head above it and two motion lines. */
  const logoMark = (cls = "who") => {
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", cls);
    svg.setAttribute("aria-hidden", "true");
    const part = (tag, attrs) => {
      const el = document.createElementNS(NS, tag);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      svg.append(el);
    };
    part("path", { class: "mk-j", d: "M13 9v6.5a5 5 0 0 1-10 0" });
    part("circle", { class: "mk-head", cx: "13", cy: "4.3", r: "2.3" });
    part("path", { class: "mk-lines", d: "M17.5 8.5h3.5M17.5 13h3.5" });
    return svg;
  };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* private mode */ } },
  };

  let markdownReady = false;
  function renderMarkdown(text) {
    const src = String(text ?? "");
    if (window.marked && window.DOMPurify) {
      if (!markdownReady) {
        window.marked.setOptions({ gfm: true, breaks: true });
        window.DOMPurify.addHook("afterSanitizeAttributes", (node) => {
          if (node.tagName === "A") { node.setAttribute("target", "_blank"); node.setAttribute("rel", "noopener noreferrer"); }
        });
        markdownReady = true;
      }
      return h("div", { class: "md", html: window.DOMPurify.sanitize(window.marked.parse(src)) });
    }
    return h("div", { class: "md", style: "white-space:pre-wrap" }, src);
  }

  /** The agent sometimes returns "[{'type': 'text', 'text': ...}]" as a string; pull the text out. */
  function extractText(raw) {
    if (!raw) return "";
    if (Array.isArray(raw) && raw[0] && typeof raw[0] === "object" && "text" in raw[0]) return raw[0].text;
    if (typeof raw === "string") {
      const s = raw.trim();
      if (s.startsWith("[{")) {
        const m = s.match(/['"]text['"]\s*:\s*(['"])([\s\S]*?)\1\s*[,}]/);
        if (m) return m[2].replace(/\\n/g, "\n").replace(/\\'/g, "'").replace(/\\"/g, '"');
      }
      return raw;
    }
    return typeof raw === "object" ? JSON.stringify(raw, null, 2) : String(raw);
  }

  function initials(name) {
    const parts = String(name || "?").trim().split(/\s+/).filter(Boolean);
    return ((parts[0]?.[0] || "?") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
  }

  function logoEl(url, name) {
    const fallback = h("span", { class: "logo-fallback", "aria-hidden": "true" }, initials(name));
    const bad = !url || /ghost|static\.licdn|ui-avatars/.test(url);
    if (bad) return fallback;
    const img = h("img", { class: "logo", src: url, alt: "", loading: "lazy", referrerpolicy: "no-referrer" });
    img.addEventListener("error", () => img.replaceWith(fallback), { once: true });
    return img;
  }

  let toastTimer;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.hidden = true), 3200);
  }

  function confirmDialog(title, body, okLabel = "Delete", { danger = true, cancelLabel = "Cancel" } = {}) {
    const d = $("#confirm");
    $("#confirm-title").textContent = title;
    $("#confirm-body").textContent = body;
    $("#confirm-ok").textContent = okLabel;
    $("#confirm-ok").className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
    d.querySelector('button[value="cancel"]').textContent = cancelLabel;
    d.returnValue = "";
    d.showModal();
    return new Promise((resolve) => d.addEventListener("close", () => resolve(d.returnValue === "ok"), { once: true }));
  }

  // ============================================================
  // API
  // ============================================================
  class ApiError extends Error {
    constructor(message, status, detail) { super(message); this.status = status; this.detail = detail; }
  }

  async function api(method, path, body, { form = false, query } = {}) {
    const headers = {};
    const token = store.get("jf-token");
    if (token) headers.Authorization = `Bearer ${token}`;
    let payload;
    if (form) payload = body;
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    const url = query ? `${path}?${new URLSearchParams(query)}` : path;
    let res;
    try {
      res = await fetch(url, { method, headers, body: payload });
    } catch {
      throw new ApiError("Can't reach the server. Check that the backend is running.", 0);
    }
    if (res.status === 401 && path !== "/api/login") {
      signOut("Your session expired. Sign in again.");
      throw new ApiError("Signed out", 401);
    }
    let data = null;
    const text = await res.text();
    try { data = text ? JSON.parse(text) : null; } catch { data = text; }
    if (!res.ok) {
      const detail = data && typeof data === "object" && data.detail ? data.detail : null;
      const message = typeof detail === "string" ? detail : detail?.message || `Request failed (${res.status}).`;
      throw new ApiError(message, res.status, detail);
    }
    return data;
  }

  // ============================================================
  // State
  // ============================================================
  const TIME_FILTERS = [
    { value: "qdr:d", label: "Past 24 hours" },
    { value: "qdr:w", label: "Past week" },
    { value: "qdr:m", label: "Past month" },
  ];
  const STATUS_OPTIONS = ["Applied", "Interviewed", "Pending", "Rejected", "Offer"];

  const state = {
    username: store.get("jf-user"),
    profile: null,
    sessions: [],
    sessionsLoaded: false,
    appsCount: null,
    timeFilter: store.get("jf-time") || "qdr:w",
    // chat
    chatId: null,
    history: [],
    pipeline: "idle",
    rawJobs: [],
    scoredJobs: [],
    assets: "",
    selected: new Set(),
    boards: null,    // job-board sign-in status, from /api/job-boards
    viewerUrl: null, // in Docker: the live view of the container's browser (noVNC), from /api/config
    busy: null,      // label while an agent call is running
    chatError: null, // { message, retry }
    pending: null,   // user message shown while waiting
  };

  // ============================================================
  // Auth view
  // ============================================================
  let authMode = "signin";
  function setAuthMode(mode) {
    authMode = mode;
    const up = mode === "signup";
    $("#auth-title").textContent = up ? "Create your account" : "Sign in";
    $("#auth-submit").textContent = up ? "Create account" : "Sign in";
    $("#auth-confirm-field").hidden = !up;
    $("#auth-pass-hint").hidden = !up;
    $("#auth-pass").autocomplete = up ? "new-password" : "current-password";
    $("#auth-switch-text").textContent = up ? "Already have an account?" : "New here?";
    $("#auth-switch").textContent = up ? "Sign in" : "Create an account";
    $("#auth-error").hidden = true;
    for (const i of $("#auth-form").querySelectorAll("input")) i.removeAttribute("aria-invalid");
  }

  function authError(msg, field) {
    const e = $("#auth-error");
    e.textContent = msg;
    e.hidden = false;
    $("#auth-ok").hidden = true;
    if (field) { field.setAttribute("aria-invalid", "true"); field.focus(); }
  }

  async function onAuthSubmit(ev) {
    ev.preventDefault();
    const user = $("#auth-user"), pass = $("#auth-pass"), confirm = $("#auth-confirm");
    for (const i of [user, pass, confirm]) i.removeAttribute("aria-invalid");
    $("#auth-error").hidden = true;
    const username = user.value.trim();
    if (!username) return authError("Enter a username.", user);
    if (!pass.value) return authError("Enter a password.", pass);

    const btn = $("#auth-submit");
    btn.disabled = true;
    try {
      if (authMode === "signup") {
        if (pass.value.length < 6) return authError("Use at least 6 characters for the password.", pass);
        if (pass.value !== confirm.value) return authError("The passwords don't match.", confirm);
        await api("POST", "/api/signup", { username, password: pass.value });
      }
      const data = await api("POST", "/api/login", { username, password: pass.value });
      store.set("jf-token", data.access_token);
      store.set("jf-user", data.username);
      state.username = data.username;
      pass.value = confirm.value = "";
      startApp();
    } catch (e) {
      authError(e.status === 401 ? "That username and password don't match." : e.message, e.status === 401 ? pass : null);
    } finally {
      btn.disabled = false;
    }
  }

  function signOut(message) {
    store.set("jf-token", null);
    store.set("jf-user", null);
    Object.assign(state, { username: null, profile: null, sessions: [], sessionsLoaded: false, chatId: null, history: [], pipeline: "idle", busy: null });
    $("#shell").hidden = true;
    $("#auth").hidden = false;
    setAuthMode("signin");
    if (message) authError(message);
    if (location.hash) history.replaceState(null, "", location.pathname);
    $("#auth-user").focus();
  }

  // ============================================================
  // Shell: rail, theme, chat list
  // ============================================================
  const THEMES = ["system", "light", "dark"];
  function applyTheme(t) {
    if (t === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", t);
    $("#theme-label").textContent = `Theme: ${t}`;
    $("#theme-icon").textContent = t === "dark" ? "dark_mode" : t === "light" ? "light_mode" : "contrast";
    $("#theme-toggle").setAttribute("aria-label", `Theme: ${t}. Switch theme`);
  }

  const isPhone = () => matchMedia("(max-width: 960px)").matches;
  function openRail(open) {
    const rail = $("#rail");
    rail.classList.toggle("is-open", open);
    $("#scrim").hidden = !open;
    $("#rail-open").setAttribute("aria-expanded", String(open));
    if (open) $("#new-chat").focus();
  }

  function renderAvatar() {
    const name = state.profile?.full_name || state.username || "";
    $("#avatar").textContent = initials(name).slice(0, 1);
    $("#avatar").title = name;
  }

  function renderAppsCount() {
    const c = $("#apps-count");
    c.hidden = !state.appsCount;
    c.textContent = state.appsCount || "";
  }

  let openMenu = null;
  function closeMenu() {
    if (!openMenu) return;
    openMenu.menu.remove();
    openMenu.trigger.setAttribute("aria-expanded", "false");
    openMenu = null;
  }
  function showMenu(trigger, items, cls) {
    if (openMenu?.trigger === trigger) return closeMenu();
    closeMenu();
    const menu = h("ul", { class: `menu ${cls}`, role: "menu" },
      items.map((it) => h("li", { role: "none" },
        h("button", {
          type: "button", role: it.checked === undefined ? "menuitem" : "menuitemradio",
          "aria-checked": it.checked === undefined ? null : String(it.checked),
          class: it.danger ? "danger" : null,
          onclick: () => { closeMenu(); it.action(); },
        }, it.icon ? icon(it.icon) : null, it.label, it.checked !== undefined ? icon("check", "check") : null))));
    trigger.parentElement.append(menu);
    trigger.setAttribute("aria-expanded", "true");
    openMenu = { trigger, menu };
    menu.querySelector("button")?.focus();
    menu.addEventListener("keydown", (e) => {
      const btns = [...menu.querySelectorAll("button")];
      const i = btns.indexOf(document.activeElement);
      if (e.key === "ArrowDown") { e.preventDefault(); btns[(i + 1) % btns.length].focus(); }
      if (e.key === "ArrowUp") { e.preventDefault(); btns[(i - 1 + btns.length) % btns.length].focus(); }
      if (e.key === "Escape") { closeMenu(); trigger.focus(); }
      if (e.key === "Tab") closeMenu();
    });
  }
  document.addEventListener("click", (e) => {
    if (openMenu && !openMenu.menu.contains(e.target) && !openMenu.trigger.contains(e.target)) closeMenu();
  });

  function renderChatList() {
    const list = $("#chat-list");
    list.replaceChildren();
    $("#chat-list-empty").hidden = !state.sessionsLoaded || state.sessions.length > 0;
    for (const s of state.sessions) {
      const active = s.session_id === state.chatId && route().name === "chat";
      const more = h("button", {
        class: "icon-btn chat-more", type: "button", "aria-haspopup": "menu", "aria-expanded": "false",
        "aria-label": `Options for ${s.title}`,
      }, icon("more_vert"));
      const li = h("li", { class: `chat-item menu-anchor${active ? " is-active" : ""}` },
        h("a", { class: "chat-link", href: `#/chat/${s.session_id}`, title: s.title, "aria-current": active ? "page" : null }, s.title),
        more);
      more.addEventListener("click", () => showMenu(more, [
        { label: "Rename", icon: "edit", action: () => startRename(li, s) },
        { label: "Delete", icon: "delete", danger: true, action: () => deleteChat(s) },
      ], "menu-right"));
      list.append(li);
    }
  }

  function startRename(li, s) {
    const input = h("input", { class: "chat-rename", value: s.title, "aria-label": "Chat name", maxlength: "80" });
    li.replaceChildren(input);
    input.focus();
    input.select();
    let done = false;
    const finish = async (save) => {
      if (done) return;
      done = true;
      const title = input.value.trim();
      if (save && title && title !== s.title) {
        try {
          await api("PUT", `/api/chat-sessions/${s.session_id}`, { title });
          s.title = title;
        } catch (e) { toast(e.message); }
      }
      renderChatList();
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") finish(true);
      if (e.key === "Escape") finish(false);
    });
    input.addEventListener("blur", () => finish(true));
  }

  async function deleteChat(s) {
    const ok = await confirmDialog("Delete chat?", `"${s.title}" and its search results will be removed. Applications you already logged stay in Applications.`);
    if (!ok) return;
    try {
      await api("DELETE", `/api/chat-sessions/${s.session_id}`);
      state.sessions = state.sessions.filter((x) => x.session_id !== s.session_id);
      if (state.chatId === s.session_id) location.hash = "#/chat";
      renderChatList();
      toast("Chat deleted");
    } catch (e) { toast(e.message); }
  }

  async function loadSessions() {
    try {
      state.sessions = await api("GET", "/api/chat-sessions");
    } catch { /* the list just stays as it was */ }
    state.sessionsLoaded = true;
    renderChatList();
    if (route().name === "chat" && state.chatId) {
      const s = state.sessions.find((x) => x.session_id === state.chatId);
      if (s) document.title = `${s.title} · Job Finder`;
    }
  }

  async function loadProfile() {
    try { state.profile = await api("GET", "/api/profile"); } catch { state.profile = state.profile || {}; }
    renderAvatar();
    return state.profile;
  }

  async function loadAppsCount() {
    try { state.appsCount = (await api("GET", "/api/applications")).length; } catch { /* leave it */ }
    renderAppsCount();
  }

  // ============================================================
  // Job-board sign-in (the auto-apply agent never logs in for the user)
  // ============================================================
  async function loadBoards() {
    try { state.boards = await api("GET", "/api/job-boards"); } catch { state.boards = state.boards || []; }
    return state.boards;
  }

  function boardForUrl(url) {
    let host = "";
    try { host = new URL(url).hostname.toLowerCase(); } catch { return null; }
    return (state.boards || []).find((b) => b.hosts.some((h) => host === h || host.endsWith(`.${h}`))) || null;
  }

  /** Boards the given jobs are on that the user hasn't signed in to yet. */
  function boardsMissing(jobs) {
    const out = [];
    for (const j of jobs) {
      const b = boardForUrl(j.link);
      if (b && !b.signed_in && !out.includes(b)) out.push(b);
    }
    return out;
  }

  /** Opens the board's sign-in window on this computer and waits for the user. Resolves to true when signed in. */
  async function signInBoard(board, btn, note) {
    btn.disabled = true;
    if (state.viewerUrl) {
      // Docker: the window opens on the container's virtual screen; show it in a tab (opened in the
      // click itself so the popup isn't blocked).
      window.open(state.viewerUrl, "jobfinder-browser");
      note.textContent = board.can_verify
        ? `${board.name} opened in the browser view tab. Sign in there and it closes by itself.`
        : `${board.name} opened in the browser view tab. Sign in there, then close its tab with Ctrl+W.`;
    } else {
      note.textContent = board.can_verify
        ? `A ${board.name} window opened on this computer. Sign in there and it closes by itself.`
        : `A ${board.name} window opened on this computer. Sign in there, then close the window.`;
    }
    try {
      const r = await api("POST", `/api/job-boards/${board.key}/sign-in`);
      let ok = r.signed_in;
      if (ok === null) {
        ok = await confirmDialog(`Did you sign in to ${board.name}?`,
          "The agent will apply with that account. Choose No if you closed the window before signing in.",
          "Yes, I'm signed in", { danger: false, cancelLabel: "No" });
        await api("POST", `/api/job-boards/${board.key}/confirm`, { signed_in: ok });
      }
      await loadBoards();
      note.textContent = ok ? "" : `No ${board.name} sign-in was saved. Try again and finish signing in before closing the window.`;
      if (ok) toast(`Signed in to ${board.name}`);
      return ok;
    } catch (e) {
      if (e.status !== 401) note.textContent = e.message;
      return false;
    } finally {
      btn.disabled = false;
    }
  }

  function boardRow(board, onChange) {
    const note = h("p", { class: "hint", role: "status" });
    const btn = h("button", { class: `btn ${board.signed_in ? "btn-outline" : "btn-primary"}`, type: "button" },
      board.signed_in ? "Sign in again" : `Sign in to ${board.name}`);
    btn.addEventListener("click", async () => { if (await signInBoard(board, btn, note)) onChange(); });
    const when = board.updated_at ? formatDate(board.updated_at) : "";
    return h("li", { class: "board-row" },
      h("div", { class: "board-main" },
        h("span", { class: "board-name" }, board.name),
        h("span", { class: `board-state${board.signed_in ? " ok" : ""}` },
          board.signed_in ? icon("check_circle", "fill") : null,
          board.signed_in ? `Signed in${when ? ` · ${when}` : ""}` : "Not signed in"),
        note),
      btn);
  }

  // ============================================================
  // Router
  // ============================================================
  function route() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
    if (parts[0] === "profile") return { name: "profile" };
    if (parts[0] === "applications") return { name: "applications" };
    return { name: "chat", id: parts[0] === "chat" ? parts[1] || null : null };
  }

  function setNavCurrent(name) {
    for (const a of document.querySelectorAll("[data-nav]")) {
      if (a.dataset.nav === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    }
  }

  async function onRoute() {
    closeMenu();
    if (isPhone()) openRail(false);
    const r = route();
    setNavCurrent(r.name);
    renderChatList();
    if (r.name === "profile") { document.title = "Profile · Job Finder"; return renderProfile(); }
    if (r.name === "applications") { document.title = "Applications · Job Finder"; return renderApplications(); }
    await openChat(r.id);
  }

  // ============================================================
  // Chat
  // ============================================================
  const view = () => $("#view");

  async function openChat(id) {
    if (state.busy && id === state.chatId) return renderChat();
    runTicket++;
    Object.assign(state, {
      chatId: id, history: [], pipeline: "idle", rawJobs: [], scoredJobs: [], assets: "",
      selected: new Set(), chatError: null, pending: null, busy: null,
    });
    const s = state.sessions.find((x) => x.session_id === id);
    document.title = `${s ? s.title : "New chat"} · Job Finder`;
    renderChatList();
    if (!id) return renderChat();
    renderChat({ loading: true });
    try {
      const data = await api("GET", `/api/chat-sessions/${id}/history`);
      if (state.chatId !== id) return;
      applyHistory(data);
    } catch (e) {
      if (state.chatId !== id) return;
      if (e.status === 404) { location.hash = "#/chat"; return; }
      state.chatError = { message: `Couldn't load this chat. ${e.message}`, retry: () => openChat(id) };
    }
    renderChat();
  }

  function applyHistory(data) {
    state.history = data.history || [];
    state.pipeline = data.status || "idle";
    state.rawJobs = data.raw_jobs || [];
    state.scoredJobs = data.scored_jobs || [];
    state.assets = data.tailored_assets || "";
    state.selected = new Set();
  }

  function firstName() {
    const full = state.profile?.full_name;
    return (full ? full.split(/\s+/)[0] : state.username) || "there";
  }

  function suggestions() {
    const p = state.profile || {};
    const titles = (p.preferred_job_titles || "").split(",").map((s) => s.trim()).filter(Boolean);
    const places = (p.preferred_locations || "").split(",").map((s) => s.trim()).filter(Boolean);
    const where = places[0] ? ` in ${places[0]}` : "";
    const out = [];
    for (const t of titles.slice(0, 2)) out.push({ text: `Find ${t} roles${where} posted this week`, icon: "travel_explore" });
    if (titles.length < 2) out.push({ text: `Find entry-level data and AI jobs${where}`, icon: "travel_explore" });
    out.push({ text: `Find internships${where} that match my skills`, icon: "school" });
    out.push({ text: "Which skills should I add to get more matches?", icon: "lightbulb" });
    return out.slice(0, 4);
  }

  function profileGaps() {
    const p = state.profile || {};
    const gaps = [];
    if (!p.cv_filename) gaps.push("upload your CV");
    if (!p.preferred_job_titles) gaps.push("add the roles you want");
    return gaps;
  }

  function renderGreeting() {
    const gaps = profileGaps();
    return h("section", { class: "greeting", "aria-labelledby": "greet" },
      h("h1", { id: "greet" }, `Hello, ${firstName()}`),
      h("p", { class: "greet-sub" }, "Which jobs should I find?"),
      h("div", { class: "suggestions" },
        suggestions().map((s) => h("button", {
          class: "suggestion", type: "button",
          onclick: () => send(s.text),
        }, h("span", null, s.text), icon(s.icon)))),
      gaps.length ? h("p", { class: "setup-note" },
        icon("info"),
        h("span", null, `For better matches, ${gaps.join(" and ")}.`),
        h("a", { href: "#/profile" }, "Open profile")) : null);
  }

  function renderMessage(m) {
    if (m.role === "user") return h("div", { class: "msg msg-user" }, h("div", { class: "bubble" }, m.content));
    return h("div", { class: "msg msg-ai" }, logoMark(), h("div", { class: "body" }, renderMarkdown(m.content)));
  }

  function jobRow(job, idx) {
    const checked = state.selected.has(idx);
    const id = `job-${idx}`;
    const cb = h("input", {
      type: "checkbox", id, checked, "aria-describedby": `${id}-meta`,
      "aria-label": `Select ${job.title || "this job"} at ${job.company || "unknown company"}`,
    });
    const label = h("label", { class: `job${checked ? " is-selected" : ""}`, for: id },
      cb,
      logoEl(job.logo_url, job.company),
      h("div", { class: "job-main" },
        h("span", { class: "job-title" }, job.title || "Untitled role"),
        h("span", { class: "job-meta", id: `${id}-meta` },
          h("span", null, job.company || "Unknown company"),
          job.location ? h("span", null, job.location) : null,
          job.date ? h("span", null, job.date) : null,
          job.platform ? h("span", null, job.platform) : null),
        job.snippet ? h("span", { class: "job-snippet" }, job.snippet) : null),
      job.link ? h("a", {
        class: "icon-btn job-open", href: job.link, target: "_blank", rel: "noopener noreferrer",
        "aria-label": `Open ${job.title || "job"} at ${job.company || "company"} in a new tab`,
        onclick: (e) => e.stopPropagation(),
      }, icon("open_in_new")) : h("span"));
    cb.addEventListener("change", () => {
      if (cb.checked) state.selected.add(idx); else state.selected.delete(idx);
      label.classList.toggle("is-selected", cb.checked);
      updatePickerCount();
    });
    return h("li", null, label);
  }

  function updatePickerCount() {
    const n = state.selected.size, total = state.rawJobs.length;
    const cont = $("#pick-continue");
    if (!cont) return;
    cont.disabled = n === 0 || !!state.busy;
    cont.textContent = n ? `Continue with ${n} ${n === 1 ? "job" : "jobs"}` : "Select jobs to continue";
    $("#pick-count").textContent = `${n} of ${total} selected`;
    $("#pick-all").textContent = n === total ? "Clear selection" : "Select all";
  }

  function renderPicker() {
    const jobs = state.rawJobs;
    if (!jobs.length) {
      return h("section", { class: "block" },
        h("div", { class: "empty" },
          h("p", null, "No jobs came back for that search. Try a broader title, another location or a longer time range."),
          h("button", { class: "btn btn-outline", type: "button", onclick: cancelPipeline }, "Start a new search")));
    }
    const all = h("button", { class: "btn btn-text-only", id: "pick-all", type: "button" }, "Select all");
    all.addEventListener("click", () => {
      state.selected = state.selected.size === jobs.length ? new Set() : new Set(jobs.map((_, i) => i));
      renderChat({ keepScroll: true });
    });
    const block = h("section", { class: "block", "aria-labelledby": "pick-title" },
      h("div", { class: "block-head" },
        h("h2", { id: "pick-title" }, `I found ${jobs.length} ${jobs.length === 1 ? "job" : "jobs"}. Pick the ones to apply for.`),
        h("p", null, "Your agents will score each one against your CV and draft a cover letter.")),
      h("ul", { class: "job-list" }, jobs.map(jobRow)),
      h("div", { class: "block-actions" },
        all,
        h("span", { class: "sel-count num", id: "pick-count" }),
        h("span", { class: "gap" }),
        h("button", { class: "btn btn-text-only", type: "button", onclick: cancelPipeline }, "Cancel"),
        h("button", { class: "btn btn-primary", id: "pick-continue", type: "button", onclick: submitSelection })));
    queueMicrotask(updatePickerCount);
    return block;
  }

  function matchClass(score) {
    const n = parseFloat(score);
    if (isNaN(n)) return "low";
    return n >= 75 ? "high" : n >= 50 ? "mid" : "low";
  }

  function renderSignInGate(missing) {
    const names = missing.map((b) => b.name).join(" and ");
    return h("div", { class: "signin-gate", role: "region", "aria-labelledby": "gate-title" },
      h("div", { class: "signin-gate-head" },
        icon("lock"),
        h("div", null,
          h("h3", { id: "gate-title" }, `Sign in to ${names} first`),
          h("p", null, "The agent applies with your own account and never signs in for you. You only need to do this once."))),
      h("ul", { class: "boards" }, missing.map((b) => boardRow(b, () => renderChat({ keepScroll: true })))));
  }

  function renderReview() {
    const jobs = state.scoredJobs;
    const n = jobs.length;
    if (state.boards === null) loadBoards().then(() => { if (state.pipeline === "paused_for_review") renderChat({ keepScroll: true }); });
    const missing = state.boards ? boardsMissing(jobs) : [];
    const blocked = state.boards === null || missing.length > 0;
    return h("section", { class: "block", "aria-labelledby": "review-title" },
      h("div", { class: "block-head" },
        h("h2", { id: "review-title" }, `Review ${n} ${n === 1 ? "application" : "applications"} before I apply`),
        h("p", null, "Check the match notes and the drafted materials. Nothing is submitted until you approve.")),
      n ? h("ul", { class: "score-list" }, jobs.map((j) => h("li", { class: "score" },
        logoEl(j.logo_url, j.company),
        h("div", { class: "job-main" },
          h("span", { class: "job-title" },
            j.link ? h("a", { href: j.link, target: "_blank", rel: "noopener noreferrer" }, j.title || "Untitled role") : (j.title || "Untitled role")),
          h("span", { class: "job-meta" }, h("span", null, j.company || "Unknown company")),
          j.details ? h("p", { class: "score-why" }, j.details) : null),
        j.match_score != null && j.match_score !== ""
          ? h("span", { class: `match num ${matchClass(j.match_score)}` }, `${String(j.match_score).replace(/%$/, "")}% match`)
          : null))) : null,
      state.assets ? h("details", { class: "assets" },
        h("summary", null, icon("description"), "Cover letters and resume bullets", icon("expand_more")),
        renderMarkdown(extractText(state.assets))) : null,
      missing.length ? renderSignInGate(missing) : null,
      h("div", { class: "block-actions" },
        h("span", { class: "gap" }),
        h("button", { class: "btn btn-text-only", type: "button", onclick: cancelPipeline }, "Don't apply"),
        h("button", { class: "btn btn-primary", type: "button", disabled: !!state.busy || !n || blocked, onclick: approve },
          icon("send"), `Approve and apply${n > 1 ? ` to ${n}` : ""}`)));
  }

  function renderComposer() {
    const ta = h("textarea", {
      id: "prompt", rows: "1", placeholder: "Search for jobs or ask a question",
      "aria-label": "Message", disabled: !!state.busy,
    });
    const sendBtn = h("button", { class: "send", type: "submit", "aria-label": "Send", disabled: true }, icon("arrow_upward"));
    const sync = () => {
      ta.style.height = "auto";
      ta.style.height = `${Math.min(ta.scrollHeight, 220)}px`;
      sendBtn.disabled = !ta.value.trim() || !!state.busy;
    };
    ta.addEventListener("input", sync);
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
    });
    const tf = TIME_FILTERS.find((t) => t.value === state.timeFilter) || TIME_FILTERS[1];
    const chip = h("button", { class: "chip", type: "button", "aria-haspopup": "menu", "aria-expanded": "false", "aria-label": `Job posting date: ${tf.label}` },
      icon("calendar_today"), tf.label, icon("arrow_drop_down"));
    chip.addEventListener("click", () => showMenu(chip, TIME_FILTERS.map((t) => ({
      label: t.label, checked: t.value === state.timeFilter,
      action: () => {
        state.timeFilter = t.value;
        store.set("jf-time", t.value);
        chip.replaceChildren(icon("calendar_today"), t.label, icon("arrow_drop_down"));
        chip.setAttribute("aria-label", `Job posting date: ${t.label}`);
        chip.focus();
      },
    })), "menu-up"));
    const form = h("form", { class: "composer" },
      ta,
      h("div", { class: "composer-row" },
        h("div", { class: "menu-anchor" }, chip),
        h("span", { class: "gap" }),
        sendBtn));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const text = ta.value.trim();
      if (!text || state.busy) return;
      send(text);
    });
    return h("div", { class: "composer-wrap" }, form,
      h("p", { class: "disclaimer" }, "Job Finder can make mistakes. Check each listing before you apply."));
  }

  function renderChat({ loading = false, keepScroll = false } = {}) {
    const v = view();
    const prevScroll = v.scrollTop;
    const focusedPrompt = document.activeElement?.id === "prompt";
    const draft = $("#prompt")?.value || "";
    const thread = h("div", { class: "thread", id: "thread", "aria-live": "polite", "aria-busy": String(!!state.busy || loading) });

    const title = state.sessions.find((s) => s.session_id === state.chatId)?.title || "New chat";
    document.title = `${title} · Job Finder`;
    const empty = !state.history.length && !state.pending && !loading;
    if (empty && state.pipeline === "idle") thread.append(renderGreeting());
    else thread.append(h("h1", { class: "sr-only" }, title));

    if (loading) {
      thread.append(h("div", { class: "msg msg-user" }, h("span", { class: "skeleton", style: "width:240px;height:46px;border-radius:24px" })));
      thread.append(h("div", { class: "msg msg-ai" }, logoMark(),
        h("div", { class: "body", style: "display:grid;gap:10px" },
          h("span", { class: "skeleton", style: "width:90%;height:16px" }),
          h("span", { class: "skeleton", style: "width:70%;height:16px" }),
          h("span", { class: "skeleton", style: "width:80%;height:16px" }))));
    }

    for (const m of state.history) thread.append(renderMessage(m));
    if (state.pending) thread.append(renderMessage({ role: "user", content: state.pending }));

    if (!state.busy) {
      if (state.pipeline === "paused_for_selection") thread.append(renderPicker());
      else if (state.pipeline === "paused_for_review") thread.append(renderReview());
    }

    if (state.busy) {
      // While auto-apply runs in Docker, offer the live view so CAPTCHAs can be solved there.
      const watch = state.viewerUrl && state.busy.startsWith("Applying")
        ? h("a", { href: state.viewerUrl, target: "jobfinder-browser", rel: "noopener" }, "Watch the browser")
        : null;
      thread.append(h("div", { class: "thinking", role: "status" }, logoMark(), h("span", { class: "thinking-text" }, state.busy), watch));
    }
    if (state.chatError) {
      thread.append(h("div", { class: "msg msg-ai is-error" }, logoMark(),
        h("div", { class: "body", style: "display:grid;gap:8px;justify-items:start" },
          h("p", { class: "err-line" }, icon("error"), state.chatError.message),
          state.chatError.retry ? h("button", { class: "btn btn-outline", type: "button", onclick: state.chatError.retry }, icon("refresh"), "Try again") : null)));
    }

    const composer = renderComposer();
    v.replaceChildren(h("section", { class: "chat" }, thread, composer));
    const ta = $("#prompt");
    if (draft && !state.busy) { ta.value = draft; ta.dispatchEvent(new Event("input")); }
    if (keepScroll) v.scrollTop = prevScroll;
    else v.scrollTop = v.scrollHeight;
    if (focusedPrompt || (!keepScroll && !state.busy && !isPhone())) ta.focus({ preventScroll: true });
  }

  async function ensureSession() {
    if (state.chatId) return state.chatId;
    const s = await api("POST", "/api/chat-sessions", { title: "New Chat" });
    state.chatId = s.session_id;
    state.sessions.unshift({ session_id: s.session_id, title: s.title, created_at: "" });
    history.replaceState(null, "", `#/chat/${s.session_id}`);
    renderChatList();
    return s.session_id;
  }

  async function refreshHistory() {
    const id = state.chatId;
    const data = await api("GET", `/api/chat-sessions/${id}/history`);
    if (state.chatId === id) applyHistory(data);
  }

  // Each agent call gets a ticket; switching chats issues a new one, so a late reply never lands in the wrong chat.
  let runTicket = 0;
  async function runAgent(label, fn, retry) {
    state.busy = label;
    state.chatError = null;
    renderChat();
    const ticket = ++runTicket;
    try {
      await fn();
    } catch (e) {
      if (e.status === 401) return;
      if (ticket === runTicket) {
        const message = e.status >= 500 ? `The agent ran into a problem and stopped. Server said: ${e.message}` : e.message;
        state.chatError = { message, retry };
      }
    } finally {
      if (ticket === runTicket) {
        state.busy = null;
        if (!state.chatError) state.pending = null; // keep the unanswered message on screen beside its error
        renderChat();
      }
    }
  }

  async function send(text) {
    state.pending = text;
    await runAgent("Searching and thinking…", async () => {
      const id = await ensureSession();
      try {
        await api("POST", "/api/job-finder/start", { session_id: id, query: text, time_filter: state.timeFilter });
        await refreshHistory();
      } finally {
        loadSessions(); // the backend renames a new chat after its first message, even when the agent then fails
      }
    }, () => send(text));
  }

  async function submitSelection() {
    const indices = [...state.selected].sort((a, b) => a - b);
    if (!indices.length) return;
    await runAgent(`Scoring ${indices.length} ${indices.length === 1 ? "job" : "jobs"} and drafting your application…`, async () => {
      const data = await api("POST", "/api/job-finder/select-jobs", { session_id: state.chatId, selected_indices: indices });
      await refreshHistory();
      if (data?.status === "paused_for_review") {
        state.pipeline = "paused_for_review";
        state.scoredJobs = data.scored_jobs || state.scoredJobs;
        state.assets = data.tailored_assets || state.assets;
      }
    }, submitSelection);
  }

  async function approve() {
    const jobs = state.scoredJobs;
    await runAgent(`Applying to ${jobs.length} ${jobs.length === 1 ? "job" : "jobs"}. This can take a few minutes…`, async () => {
      try {
        await api("POST", "/api/job-finder/resume", { session_id: state.chatId, feedback: "approve", jobs });
      } catch (e) {
        // The server refuses until the user has signed in to each board; show the sign-in step instead.
        if (e.status === 409 && e.detail?.boards) { await loadBoards(); toast(e.message); return; }
        throw e;
      }
      await refreshHistory();
      loadBoards(); // an expired session is marked signed-out by the agent
      state.pipeline = "idle";
      await loadAppsCount();
      toast(`Logged ${jobs.length} ${jobs.length === 1 ? "application" : "applications"}`);
    }, approve);
  }

  function cancelPipeline() {
    state.pipeline = "idle";
    state.selected = new Set();
    renderChat();
  }

  // ============================================================
  // Profile
  // ============================================================
  const PROFILE_FIELDS = [
    ["full_name", "your name"], ["email", "email"], ["university", "university"], ["degree", "degree"],
    ["gpa", "GPA"], ["skills", "skills"], ["work_experience", "experience"], ["cv_filename", "CV"],
    ["preferred_job_titles", "roles you want"], ["preferred_locations", "locations"],
  ];

  function field(id, label, value, opts = {}) {
    const { type = "text", placeholder, textarea, hint, ...rest } = opts;
    const attrs = { id, name: id, placeholder, "aria-describedby": hint ? `${id}-hint` : null, ...rest };
    const input = textarea
      ? h("textarea", { ...attrs, rows: textarea }, value ?? "")
      : h("input", { ...attrs, type, value: value ?? "" });
    return h("div", { class: "field" },
      h("label", { for: id }, label),
      input,
      hint ? h("p", { class: "hint", id: `${id}-hint` }, hint) : null);
  }

  function section(title, desc, ...content) {
    return h("section", { class: "setting", "aria-labelledby": `sec-${title.replace(/\W+/g, "-")}` },
      h("div", { class: "setting-label" }, h("h2", { id: `sec-${title.replace(/\W+/g, "-")}` }, title), h("p", null, desc)),
      h("div", { class: "setting-panel" }, ...content));
  }

  function renderProgress(p) {
    const filled = PROFILE_FIELDS.filter(([k]) => p[k]).length;
    const missing = PROFILE_FIELDS.filter(([k]) => !p[k]).map(([, l]) => l);
    const pct = Math.round((filled / PROFILE_FIELDS.length) * 100);
    return h("div", { class: "progress", id: "progress" },
      h("div", { class: "progress-row" },
        h("strong", null, "Profile strength"),
        h("span", { class: "num" }, `${filled} of ${PROFILE_FIELDS.length} filled`)),
      h("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(pct), "aria-label": "Profile strength" },
        h("span", { style: `width:${pct}%` })),
      h("p", { class: "progress-missing" }, missing.length ? `Still missing: ${missing.join(", ")}.` : "Complete. Your agents have everything they need."));
  }

  async function renderProfile() {
    const v = view();
    v.replaceChildren(h("div", { class: "page" },
      h("header", { class: "page-head" }, h("div", null, h("h1", null, "Profile"), h("p", null, "Your agents use this to choose, score and tailor applications."))),
      h("div", { class: "progress" }, h("span", { class: "skeleton", style: "width:40%;height:16px" }), h("span", { class: "skeleton", style: "height:6px" }))));
    v.scrollTop = 0;

    let p;
    try { p = await api("GET", "/api/profile"); state.profile = p; renderAvatar(); }
    catch (e) {
      if (e.status === 401) return;
      v.querySelector(".progress").replaceWith(h("div", { class: "inline-error" }, icon("error"),
        h("span", null, `Couldn't load your profile. ${e.message}`), h("span", { class: "gap" }),
        h("button", { class: "btn btn-text-only", type: "button", onclick: renderProfile }, "Try again")));
      return;
    }
    if (route().name !== "profile") return;

    const form = h("form", { class: "settings", id: "profile-form", novalidate: true },
      section("About you", "How employers will reach you.",
        field("full_name", "Full name", p.full_name, { autocomplete: "name" }),
        h("div", { class: "grid-2" },
          field("email", "Email", p.email, { type: "email", autocomplete: "email" }),
          field("phone", "Phone", p.phone, { type: "tel", autocomplete: "tel", placeholder: "+66 81 234 5678" }))),
      section("Education", "Used to match graduate and entry-level roles.",
        field("university", "University", p.university, { placeholder: "Chulalongkorn University" }),
        field("degree", "Degree", p.degree, { placeholder: "B.Sc. Computer Science" }),
        h("div", { class: "grid-2" },
          field("gpa", "GPA", p.gpa, { type: "number", min: "0", max: "4", step: "0.01", inputmode: "decimal", hint: "Out of 4.00. Leave empty to skip." }),
          field("graduation_year", "Graduation year", p.graduation_year, { type: "number", min: "2000", max: "2035", step: "1", inputmode: "numeric" }))),
      section("Skills and experience", "The scoring agent compares these with each job description.",
        field("skills", "Skills", p.skills, { textarea: 3, placeholder: "Python, SQL, PyTorch, LangChain, Docker", hint: "Separate skills with commas." }),
        field("work_experience", "Experience", p.work_experience, { textarea: 5, placeholder: "Internships, jobs and projects, with what you did and the result." })),
      section("Links", "Added to applications that ask for them.",
        h("div", { class: "grid-2" },
          field("linkedin_url", "LinkedIn", p.linkedin_url, { type: "url", placeholder: "https://linkedin.com/in/you" }),
          field("github_url", "GitHub", p.github_url, { type: "url", placeholder: "https://github.com/you" }))),
      section("What you're looking for", "Your agents search for these when you don't say otherwise.",
        field("preferred_job_titles", "Roles", p.preferred_job_titles, { placeholder: "Data Scientist, ML Engineer", hint: "Separate roles with commas." }),
        field("preferred_locations", "Locations", p.preferred_locations, { placeholder: "Bangkok, Remote", hint: "Separate locations with commas." })),
      h("div", { class: "save-bar" },
        h("span", { class: "save-state", id: "save-state", role: "status" }),
        h("button", { class: "btn btn-primary", type: "submit", id: "save-btn" }, "Save changes")));

    form.addEventListener("input", () => { $("#save-state").className = "save-state"; $("#save-state").textContent = "Unsaved changes"; });
    form.addEventListener("submit", saveProfile);

    v.replaceChildren(h("div", { class: "page" },
      h("header", { class: "page-head" }, h("div", null, h("h1", null, "Profile"), h("p", null, "Your agents use this to choose, score and tailor applications."))),
      renderProgress(p),
      h("div", { class: "settings" }, renderCvSection(p), renderBoardsSection()),
      form));
  }

  function renderBoardsSection() {
    const list = h("ul", { class: "boards" }, h("li", { class: "board-row" }, h("span", { class: "skeleton", style: "width:40%;height:16px" })));
    const draw = () => list.replaceChildren(...(state.boards || []).map((b) => boardRow(b, draw)));
    loadBoards().then(draw);
    return h("section", { class: "setting", "aria-labelledby": "sec-boards" },
      h("div", { class: "setting-label" },
        h("h2", { id: "sec-boards" }, "Job board sign-in"),
        h("p", null, "Sign in once on each site you want to auto-apply on. The agent uses these sessions and never logs in for you. The window opens on the computer running Job Finder.")),
      h("div", { class: "setting-panel" }, list));
  }

  async function saveProfile(e) {
    e.preventDefault();
    const f = e.currentTarget;
    const val = (k) => f.elements[k].value.trim() || null;
    const gpaRaw = val("gpa");
    const gpa = gpaRaw == null ? null : Number(gpaRaw);
    if (gpa != null && (isNaN(gpa) || gpa < 0 || gpa > 4)) {
      f.elements.gpa.setAttribute("aria-invalid", "true");
      f.elements.gpa.focus();
      $("#save-state").textContent = "GPA must be between 0.00 and 4.00.";
      return;
    }
    f.elements.gpa.removeAttribute("aria-invalid");
    const year = val("graduation_year");
    const payload = {
      full_name: val("full_name"), email: val("email"), phone: val("phone"),
      university: val("university"), degree: val("degree"),
      gpa: gpa || null, graduation_year: year ? parseInt(year, 10) : null,
      skills: val("skills"), work_experience: val("work_experience"),
      linkedin_url: val("linkedin_url"), github_url: val("github_url"),
      preferred_job_titles: val("preferred_job_titles"), preferred_locations: val("preferred_locations"),
    };
    const btn = $("#save-btn"), st = $("#save-state");
    btn.disabled = true;
    st.className = "save-state";
    st.textContent = "Saving…";
    try {
      await api("PUT", "/api/profile", payload);
      Object.assign(state.profile, payload);
      renderAvatar();
      $("#progress").replaceWith(renderProgress(state.profile));
      st.className = "save-state ok";
      st.replaceChildren(icon("check_circle"), "Saved");
    } catch (err) {
      st.textContent = `Couldn't save. ${err.message}`;
    } finally {
      btn.disabled = false;
    }
  }

  function renderCvSection(p) {
    const wrap = h("div", { class: "setting-panel", id: "cv-panel" });
    const draw = () => {
      wrap.replaceChildren();
      const name = p.cv_filename;
      if (name) {
        wrap.append(h("div", { class: "cv-file" },
          icon("picture_as_pdf"),
          h("span", { class: "name", title: name }, name),
          h("button", {
            class: "btn btn-text-only", type: "button",
            onclick: async () => {
              const ok = await confirmDialog("Remove CV?", `${name} will be deleted and your agents will stop using it for matching.`, "Remove");
              if (!ok) return;
              try {
                await api("DELETE", "/api/profile/cv");
                p.cv_filename = null;
                draw();
                $("#progress").replaceWith(renderProgress(p));
                toast("CV removed");
              } catch (e) { toast(e.message); }
            },
          }, "Remove")));
      }
      const input = h("input", { type: "file", accept: "application/pdf,.pdf", id: "cv-input", "aria-describedby": "cv-hint" });
      const status = h("p", { class: "hint", id: "cv-hint" }, "PDF only. Uploading replaces the current CV.");
      const drop = h("label", { class: "drop", for: "cv-input" },
        icon("upload_file"),
        h("strong", null, name ? "Upload a new CV" : "Upload your CV"),
        h("span", null, "Drop a PDF here or click to choose one"),
        input);
      const upload = async (file) => {
        if (!file) return;
        if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") {
          status.textContent = "That file isn't a PDF. Choose a .pdf file.";
          return;
        }
        drop.style.pointerEvents = "none";
        status.textContent = `Uploading and reading ${file.name}…`;
        const fd = new FormData();
        fd.append("file", file, file.name);
        try {
          await api("POST", "/api/upload-resume", fd, { form: true, query: { session_id: state.chatId || "profile" } });
          p.cv_filename = file.name;
          draw();
          $("#progress").replaceWith(renderProgress(p));
          toast("CV uploaded and processed");
        } catch (e) {
          status.textContent = `Upload failed. ${e.message}`;
          drop.style.pointerEvents = "";
        }
      };
      input.addEventListener("change", () => upload(input.files[0]));
      drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("is-over"); });
      drop.addEventListener("dragleave", () => drop.classList.remove("is-over"));
      drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("is-over"); upload(e.dataTransfer.files[0]); });
      wrap.append(drop, status);
    };
    draw();
    return h("section", { class: "setting", "aria-labelledby": "sec-cv" },
      h("div", { class: "setting-label" }, h("h2", { id: "sec-cv" }, "CV"), h("p", null, "Read once and stored so your agents can quote your real experience.")),
      wrap);
  }

  // ============================================================
  // Applications
  // ============================================================
  let appsFilter = "All";

  function statusTone(s) {
    const v = String(s || "").toLowerCase();
    if (v === "offer") return "positive";
    if (v === "interviewed") return "info";
    if (v === "pending" || v.includes("manual") || v.includes("sign-in")) return "warning";
    if (v === "rejected" || v.startsWith("failed")) return "negative";
    return "neutral";
  }

  function formatDate(ts) {
    if (!ts) return "";
    const d = new Date(ts.replace(" ", "T"));
    if (isNaN(d)) return ts;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  }

  async function renderApplications() {
    const v = view();
    const head = (count) => h("header", { class: "page-head" },
      h("div", null, h("h1", null, "Applications"),
        h("p", { class: "num" }, !count ? "Every job you approved, and where it stands." : `${count} ${count === 1 ? "application" : "applications"}. Update the status as you hear back.`)),
      h("a", { class: "btn btn-outline", href: "#/chat" }, icon("travel_explore"), "Find more jobs"));
    v.replaceChildren(h("div", { class: "page" }, head(null),
      h("ul", { class: "apps" }, [0, 1, 2].map(() => h("li", { class: "app-row" },
        h("span", { class: "skeleton", style: "width:40px;height:40px;border-radius:10px" }),
        h("div", { class: "app-main" }, h("span", { class: "skeleton", style: "width:50%;height:16px" }), h("span", { class: "skeleton", style: "width:30%;height:13px;margin-top:6px" })),
        h("span", { class: "skeleton", style: "width:120px;height:34px;border-radius:999px" }), h("span"))))));
    v.scrollTop = 0;

    let apps;
    try { apps = await api("GET", "/api/applications"); }
    catch (e) {
      if (e.status === 401) return;
      v.querySelector(".apps").replaceWith(h("div", { class: "inline-error" }, icon("error"),
        h("span", null, `Couldn't load applications. ${e.message}`), h("span", { class: "gap" }),
        h("button", { class: "btn btn-text-only", type: "button", onclick: renderApplications }, "Try again")));
      return;
    }
    if (route().name !== "applications") return;
    drawApplications(apps, head);
  }

  /** Draws the list from data already loaded, so a status change or delete updates counts without a refetch. */
  function drawApplications(apps, head, focusId) {
    state.appsCount = apps.length;
    renderAppsCount();

    const redraw = (id) => drawApplications(apps, head, id);
    const page = h("div", { class: "page" }, head(apps.length));
    if (!apps.length) {
      page.append(h("div", { class: "empty" },
        h("p", null, "No applications yet. Search for jobs, pick the ones you like and approve them, and they'll be tracked here."),
        h("a", { class: "btn btn-primary", href: "#/chat" }, "Find jobs")));
      return view().replaceChildren(page);
    }

    const counts = { All: apps.length };
    for (const a of apps) counts[a.status] = (counts[a.status] || 0) + 1;
    if (!counts[appsFilter]) appsFilter = "All";
    const filters = h("div", { class: "filters", role: "group", "aria-label": "Filter by status" },
      Object.entries(counts).map(([name, n]) => h("button", {
        class: "filter", type: "button", id: `filter-${name.replace(/\W+/g, "-")}`, "aria-pressed": String(name === appsFilter),
        onclick: (e) => { appsFilter = name; redraw(e.currentTarget.id); },
      }, name, h("span", { class: "n" }, n))));

    const list = h("ul", { class: "apps" });
    for (const a of apps.filter((x) => appsFilter === "All" || x.status === appsFilter)) list.append(appRow(a, apps, redraw));
    page.append(filters, list);
    view().replaceChildren(page);
    if (focusId) document.getElementById(focusId)?.focus();
  }

  function appRow(a, all, redraw) {
    const opts = STATUS_OPTIONS.includes(a.status) ? STATUS_OPTIONS : [...STATUS_OPTIONS, a.status];
    const select = h("select", { id: `status-${a.id}`, class: `st-${statusTone(a.status)}`, "aria-label": `Status for ${a.job_title} at ${a.company}` },
      opts.map((o) => h("option", { value: o, selected: o === a.status }, o)));
    select.addEventListener("change", async () => {
      const prev = a.status, next = select.value;
      select.className = `st-${statusTone(next)}`;
      try {
        await api("PUT", `/api/applications/${a.id}/status`, { status: next });
        a.status = next;
        toast(`Marked as ${next}`);
        redraw(appsFilter === "All" ? select.id : "filter-All");
      } catch (e) {
        select.value = prev;
        select.className = `st-${statusTone(prev)}`;
        toast(`Couldn't update the status. ${e.message}`);
      }
    });

    const preview = extractText(a.assets_preview);
    const assetsId = `assets-${a.id}`;
    const assets = h("div", { class: "app-assets", id: assetsId, hidden: true }, preview ? renderMarkdown(preview) : null);
    const toggle = preview ? h("button", {
      class: "icon-btn", type: "button", "aria-expanded": "false", "aria-controls": assetsId,
      "aria-label": `Show the drafted materials for ${a.job_title}`,
    }, icon("description")) : null;
    toggle?.addEventListener("click", () => {
      const open = assets.hidden;
      assets.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
    });

    const del = h("button", { class: "icon-btn", type: "button", "aria-label": `Delete ${a.job_title} at ${a.company}` }, icon("delete"));
    del.addEventListener("click", async () => {
      const ok = await confirmDialog("Delete application?", `${a.job_title} at ${a.company} will be removed from your tracker. This doesn't withdraw it from the employer.`);
      if (!ok) return;
      try {
        await api("DELETE", `/api/applications/${a.id}`);
        all.splice(all.indexOf(a), 1);
        toast("Application deleted");
        redraw("filter-All");
      } catch (e) { toast(e.message); }
    });

    return h("li", null,
      h("div", { class: "app-row" },
        logoEl(a.logo_url, a.company),
        h("div", { class: "app-main" },
          h("span", { class: "app-title", title: a.job_title }, a.job_title),
          h("span", { class: "app-meta" }, [a.company, formatDate(a.timestamp)].filter(Boolean).join(" · "))),
        h("div", { class: "app-status" }, select, icon("expand_more")),
        h("div", { class: "app-actions" }, toggle, del)),
      assets);
  }

  // ============================================================
  // Boot
  // ============================================================
  function startApp() {
    $("#auth").hidden = true;
    $("#shell").hidden = false;
    renderAvatar();
    api("GET", "/api/config").then((c) => { state.viewerUrl = c?.browser_viewer_url || null; }).catch(() => {});
    Promise.all([loadProfile(), loadSessions(), loadAppsCount()]).then(() => {
      // Redraw the greeting with the user's name once the profile is in (new chat only).
      if (route().name === "chat" && !state.chatId && !state.busy && !state.pending) renderChat();
    });
    onRoute();
  }

  function boot() {
    // Auth view
    $("#auth-form").addEventListener("submit", onAuthSubmit);
    $("#auth-switch").addEventListener("click", () => { setAuthMode(authMode === "signin" ? "signup" : "signin"); $("#auth-user").focus(); });

    // Shell
    let theme = store.get("jf-theme") || "system";
    applyTheme(theme);
    $("#theme-toggle").addEventListener("click", () => {
      theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
      store.set("jf-theme", theme === "system" ? null : theme);
      applyTheme(theme);
    });
    const syncRailToggle = () => {
      const collapsed = document.documentElement.getAttribute("data-rail") === "collapsed";
      $("#rail-toggle").setAttribute("aria-expanded", String(!collapsed));
      $("#rail-toggle").setAttribute("aria-label", collapsed ? "Expand menu" : "Collapse menu");
    };
    syncRailToggle();
    $("#rail-toggle").addEventListener("click", () => {
      const collapsed = document.documentElement.getAttribute("data-rail") !== "collapsed";
      if (collapsed) document.documentElement.setAttribute("data-rail", "collapsed");
      else document.documentElement.removeAttribute("data-rail");
      store.set("jf-rail", collapsed ? "collapsed" : null);
      syncRailToggle();
    });
    $("#rail-open").addEventListener("click", () => openRail(true));
    $("#scrim").addEventListener("click", () => openRail(false));
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && $("#rail").classList.contains("is-open")) { openRail(false); $("#rail-open").focus(); } });
    $("#sign-out").addEventListener("click", () => signOut());
    $("#new-chat").addEventListener("click", (e) => {
      // Clicking New chat while already on a new chat should still reset it.
      if (route().name === "chat" && !route().id) { e.preventDefault(); openChat(null); if (isPhone()) openRail(false); }
    });
    window.addEventListener("hashchange", () => { if (store.get("jf-token")) onRoute(); });

    if (store.get("jf-token")) startApp();
    else { $("#auth").hidden = false; setAuthMode("signin"); $("#auth-user").focus(); }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
