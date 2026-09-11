/* ==========================================================================
 * Weave 控制台 · 前端逻辑
 * 纯原生 ES2020+，无依赖。模块化拆为 state、dom、http、feature 子模块。
 * ========================================================================== */

(() => {
  "use strict";

  /* ---------------------------------------------------------------------- *
   * 小工具
   * ---------------------------------------------------------------------- */

  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const fmt = {
    size(bytes) {
      if (bytes === 0 || bytes == null) return "0 B";
      const k = 1024;
      const units = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(k)));
      return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 2) + " " + units[i];
    },
    time(ts) {
      if (!ts) return "--";
      const d = new Date(typeof ts === "number" && ts < 1e12 ? ts * 1000 : Number(ts));
      if (isNaN(d.getTime())) return "--";
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
             `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    },
    shortTime(ts) {
      if (!ts) return "--";
      const d = new Date(typeof ts === "number" && ts < 1e12 ? ts * 1000 : Number(ts));
      if (isNaN(d.getTime())) return "--";
      const pad = (n) => String(n).padStart(2, "0");
      return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
             `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    },
    json(obj) {
      try { return JSON.stringify(obj, null, 2); } catch { return String(obj); }
    },
  };

  const escapeHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));

  const debounce = (fn, wait = 200) => {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(null, args), wait);
    };
  };

  /* ---------------------------------------------------------------------- *
   * 网络层
   * ---------------------------------------------------------------------- */

  const http = {
    async get(url) {
      const r = await fetch(url);
      const data = await r.json().catch(() => null);
      return { ok: r.ok, status: r.status, data };
    },
    async send(method, url, body, headers = {}) {
      const opts = { method, headers };
      if (body !== undefined && body !== null) {
        if (body instanceof FormData) {
          opts.body = body;
        } else {
          opts.headers["Content-Type"] = "application/json";
          opts.body = JSON.stringify(body);
        }
      }
      const r = await fetch(url, opts);
      const data = await r.json().catch(() => null);
      return { ok: r.ok, status: r.status, data };
    },
    del(url) { return this.send("DELETE", url); },
    post(url, body) { return this.send("POST", url, body); },
    put(url, body) { return this.send("PUT", url, body); },
  };

  /* ---------------------------------------------------------------------- *
   * Toast
   * ---------------------------------------------------------------------- */

  const toast = (() => {
    const stack = $("#toastStack");
    const show = (message, type = "info", ttl = 2800) => {
      const el = document.createElement("div");
      el.className = `toast ${type}`;
      el.innerHTML = `<span class="toast-dot"></span><span class="toast-text"></span>`;
      el.querySelector(".toast-text").textContent = message;
      stack.appendChild(el);
      setTimeout(() => {
        el.style.transition = "opacity 0.2s";
        el.style.opacity = "0";
        setTimeout(() => el.remove(), 220);
      }, ttl);
    };
    return {
      success: (m) => show(m, "success"),
      error:   (m) => show(m, "error", 4200),
      info:    (m) => show(m, "info"),
      warn:    (m) => show(m, "warn", 3600),
    };
  })();

  /* ---------------------------------------------------------------------- *
   * 模态框
   * ---------------------------------------------------------------------- */

  const modal = (() => {
    const root = $("#modalRoot");
    const title = $("#modalTitle");
    const body = $("#modalBody");
    const foot = $("#modalFoot");

    let onCloseCb = null;

    const close = () => {
      root.hidden = true;
      body.innerHTML = "";
      foot.innerHTML = "";
      if (onCloseCb) { onCloseCb(); onCloseCb = null; }
    };

    root.addEventListener("click", (e) => {
      if (e.target.matches("[data-close]")) close();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !root.hidden) close();
    });

    return {
      open({ title: t, content, actions = [], onClose }) {
        title.textContent = t || "";
        body.innerHTML = "";
        if (typeof content === "string") body.innerHTML = content;
        else if (content instanceof Node) body.appendChild(content);

        foot.innerHTML = "";
        actions.forEach((a) => {
          const btn = document.createElement("button");
          btn.className = `btn ${a.variant || ""}`;
          btn.textContent = a.label;
          btn.addEventListener("click", () => a.onClick({ close }));
          foot.appendChild(btn);
        });

        onCloseCb = onClose || null;
        root.hidden = false;
      },
      close,
    };
  })();

  /* ---------------------------------------------------------------------- *
   * 主题
   * ---------------------------------------------------------------------- */

  const theme = (() => {
    const KEY = "weave.theme";
    const apply = (t) => {
      document.documentElement.setAttribute("data-theme", t);
      try { localStorage.setItem(KEY, t); } catch {}
    };
    let saved;
    try { saved = localStorage.getItem(KEY); } catch {}
    apply(saved || "dark");

    $("#themeBtn").addEventListener("click", () => {
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      apply(cur === "dark" ? "light" : "dark");
    });
  })();

  /* ---------------------------------------------------------------------- *
   * 全局状态
   * ---------------------------------------------------------------------- */

  const state = {
    tab: "dashboard",
    status: null,
    stats: {},
    messages: [],
    msgOffset: 0,
    msgType: "",
    files: [],
    tasks: [],
    plugins: [],
    traces: [],
    debug: {
      endpoint: "/bot/sendMessage",
      payload: "",
      result: "// 等待发送…",
      loading: false,
      lastLatencyMs: null,
    },
    debugFile: null,
    debugFileName: null,
  };

  const ENDPOINTS = [
    {
      path: "/bot/sendMessage",
      method: "POST",
      defaults: { text: "Hello from WebUI" },
    },
    {
      path: "/bot/sendPhoto",
      method: "POST",
      defaults: { photo: "storage/test.jpg", caption: "图片备注" },
    },
    {
      path: "/bot/sendDocument",
      method: "POST",
      defaults: { document: "storage/test.pdf", caption: "文件备注" },
    },
    {
      path: "/bot/getUpdates",
      method: "GET",
      defaults: { limit: 10, offset: 0 },
    },
    {
      path: "/bot/getMe",
      method: "GET",
      defaults: {},
    },
  ];

  /* ---------------------------------------------------------------------- *
   * 渲染：导航 / 页面切换
   * ---------------------------------------------------------------------- */

  const renderNav = () => {
    $$(".nav-item").forEach((b) => {
      b.classList.toggle("is-active", b.dataset.tab === state.tab);
    });
    $$(".page").forEach((p) => {
      p.classList.toggle("is-active", p.dataset.page === state.tab);
    });
  };

  $$(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.tab = btn.dataset.tab;
      renderNav();
      loadTabData();
    });
  });

  $("#refreshBtn").addEventListener("click", async () => {
    toast.info("刷新中…");
    await refreshAll();
    toast.success("已同步");
  });

  /* ---------------------------------------------------------------------- *
   * 顶部连接状态 + 侧栏元信息
   * ---------------------------------------------------------------------- */

  const renderStatus = () => {
    const s = state.status || {};
    const pill = $("#connPill");
    const txt = pill.querySelector(".status-text");

    if (!s) {
      pill.dataset.state = "loading";
      txt.textContent = "连接中";
    } else if (s.logged_in) {
      pill.dataset.state = "online";
      txt.textContent = "已登录";
    } else if (s.login_code === 408 || s.login_status === "qr_ready") {
      pill.dataset.state = "warning";
      txt.textContent = "等待扫码";
    } else {
      pill.dataset.state = "offline";
      txt.textContent = s.login_status_text || "未登录";
    }

    $("#uptime").textContent = s.uptime_str || "--";
    $("#entryHost").textContent = s.entry_host || "--";
    $("#loginCode").textContent = s.login_code ?? "--";
  };

  /* ---------------------------------------------------------------------- *
   * Dashboard
   * ---------------------------------------------------------------------- */

  const renderStats = () => {
    const s = state.stats || {};
    $("#statMessages").textContent = s.message_count ?? 0;
    $("#statToday").textContent    = s.today_message_count ?? 0;
    $("#statFiles").textContent    = s.file_count ?? 0;

    const plug = s.plugins_count ?? (Array.isArray(state.plugins) ? state.plugins.length : 0);
    const task = s.tasks_count    ?? (Array.isArray(state.tasks) ? state.tasks.length : 0);
    $("#statPlugTask").textContent = `${plug} / ${task}`;

    $("#statMessagesFoot").textContent = s.today_message_count != null
      ? `今日 +${s.today_message_count}` : "—";
    $("#statTodayFoot").textContent = "近 24 小时";
    $("#statFilesFoot").textContent = "已下载文件";
    $("#statPlugTaskFoot").textContent = "插件 / 任务";

    // 二维码区域（登录态来自 /webui/status，不在 store stats 里）
    const qr = $("#qrCard");
    const img = $("#qrImg");
    const status = $("#qrStatus");
    const tip = $("#qrTip");
    const login = state.status;

    if (login && login.logged_in) {
      qr.dataset.state = "logged";
      status.textContent = "微信已在线";
      tip.textContent = "正在稳定接收消息中…";
      img.removeAttribute("src");
    } else if (state.qrBase64) {
      qr.dataset.state = "ready";
      img.src = "data:image/png;base64," + state.qrBase64;
      const age = (login && login.uuid_age) ?? 0;
      const remain = Math.max(0, 240 - age);
      status.textContent = "等待扫码…";
      tip.textContent = `二维码剩余有效时间 ${remain}s，过期后请刷新。`;
    } else {
      qr.dataset.state = "loading";
      status.textContent = "等待二维码…";
      tip.textContent = "二维码 240 秒内有效，过期请刷新。";
    }
  };

  // --- 快速调试 ---
  $("#btnSendQuick").addEventListener("click", async () => {
    const input = $("#quickText");
    const text = input.value.trim();
    if (!text) { toast.warn("内容不能为空"); return; }
    const btn = $("#btnSendQuick");
    btn.disabled = true;
    try {
      // /send 期望 { content }
      const r = await http.post("/send", { content: text });
      if (r.ok && r.data && r.data.ok !== false) {
        toast.success("已发送");
        input.value = "";
        setTimeout(() => loadMessages(false), 600);
      } else {
        toast.error("发送失败：" + (r.data && r.data.description || r.status));
      }
    } catch (e) {
      toast.error("发送失败：" + e.message);
    } finally {
      btn.disabled = false;
    }
  });

  $("#quickText").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("#btnSendQuick").click();
  });

  $$(".quick-btn[data-cmd]").forEach((b) => {
    b.addEventListener("click", () => executeCommand(b.dataset.cmd));
  });

  $("#btnSaveSession").addEventListener("click", async () => {
    try {
      await http.post("/wechat/session/save", {});
      toast.success("Session 已落盘");
    } catch (e) { toast.error("保存失败：" + e.message); }
  });

  $("#btnReloadPlugins").addEventListener("click", async () => {
    try {
      const r = await http.post("/plugins/reload", {});
      toast.success("已重新加载");
      await loadPlugins();
    } catch (e) { toast.error("重载失败：" + e.message); }
  });

  $("#btnRefreshQr").addEventListener("click", () => refreshQr());

  /* ---------------------------------------------------------------------- *
   * 消息流
   * ---------------------------------------------------------------------- */

  const renderMessages = () => {
    const tbody = $("#msgTbody");
    if (!state.messages.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="4">暂无消息</td></tr>`;
      $("#msgCount").hidden = true;
      return;
    }
    $("#msgCount").hidden = false;
    $("#msgCount").textContent = state.messages.length;
    tbody.innerHTML = state.messages.map((m) => `
      <tr>
        <td class="col-time">${escapeHtml(fmt.shortTime(m.created_at))}</td>
        <td><span class="badge ${escapeHtml(m.type || "other")}">${escapeHtml(m.type || "?")}</span></td>
        <td title="${escapeHtml(m.text || "")}">${escapeHtml(m.text || "[附件消息]")}</td>
        <td class="col-action">
          <button class="btn btn-sm btn-quiet" data-act="detail" data-id="${escapeHtml(m.id)}">详情</button>
        </td>
      </tr>
    `).join("");
  };

  $$("#msgTbody").forEach(() => {}); // placeholder
  $("#msgTbody").addEventListener("click", (e) => {
    const btn = e.target.closest('[data-act="detail"]');
    if (!btn) return;
    const msg = state.messages.find((m) => String(m.id) === btn.dataset.id);
    if (msg) showMsgDetail(msg);
  });

  $$(".seg-item").forEach((b) => {
    b.addEventListener("click", () => {
      $$(".seg-item").forEach((x) => x.classList.remove("is-active"));
      b.classList.add("is-active");
      state.msgType = b.dataset.type || "";
      loadMessages(false);
    });
  });

  $("#btnLoadMore").addEventListener("click", () => loadMessages(true));

  /* ---------------------------------------------------------------------- *
   * Bot API 调试
   * ---------------------------------------------------------------------- */

  const renderEndpoints = () => {
    const sel = $("#epSelect");
    sel.innerHTML = ENDPOINTS.map((e) => {
      const label = e.path.replace("/bot/", "");
      return `<option value="${e.path}">${escapeHtml(label)}</option>`;
    }).join("");
    sel.value = state.debug.endpoint;
    updateEndpointMeta();
  };

  const updateEndpointMeta = () => {
    const ep = ENDPOINTS.find((e) => e.path === state.debug.endpoint) || ENDPOINTS[0];
    $("#epMethod").textContent = ep.method;
    if (!state.debug.payload) {
      state.debug.payload = fmt.json(ep.defaults);
      $("#payload").value = state.debug.payload;
    }
  };

  $("#epSelect").addEventListener("change", () => {
    state.debug.endpoint = $("#epSelect").value;
    state.debug.payload = "";
    updateEndpointMeta();
  });

  $("#payload").addEventListener("input", (e) => {
    state.debug.payload = e.target.value;
  });

  $("#btnResetPayload").addEventListener("click", () => {
    const ep = ENDPOINTS.find((e) => e.path === state.debug.endpoint) || ENDPOINTS[0];
    state.debug.payload = fmt.json(ep.defaults);
    $("#payload").value = state.debug.payload;
  });

  $("#btnSendRequest").addEventListener("click", runDebug);
  $("#btnCopyResp").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(state.debug.result);
      toast.success("已复制");
    } catch { toast.error("复制失败"); }
  });

  const setResp = (text, latencyMs) => {
    state.debug.result = text;
    $("#respView").textContent = text;
    $("#latency").textContent = latencyMs != null ? `${latencyMs} ms` : "";
  };

  async function runDebug() {
    const ep = ENDPOINTS.find((e) => e.path === state.debug.endpoint) || ENDPOINTS[0];
    const btn = $("#btnSendRequest");
    btn.disabled = true;
    setResp("// 请求中…", null);
    const t0 = performance.now();
    try {
      let parsed = {};
      try { parsed = state.debug.payload ? JSON.parse(state.debug.payload) : {}; }
      catch (e) { throw new Error("JSON 解析失败：" + e.message); }

      let url = ep.path;
      const opts = { method: ep.method, headers: {} };
      if (ep.method === "POST") {
        opts.headers["Content-Type"] = "application/json";
        opts.body = JSON.stringify(parsed);
      } else {
        const qs = new URLSearchParams(parsed).toString();
        if (qs) url += "?" + qs;
      }
      const r = await fetch(url, opts);
      const data = await r.json().catch(() => null);
      const ms = Math.round(performance.now() - t0);
      setResp(fmt.json(data ?? `HTTP ${r.status}`), ms);
    } catch (e) {
      const ms = Math.round(performance.now() - t0);
      setResp("ERROR: " + e.message, ms);
    } finally {
      btn.disabled = false;
    }
  }

  /* ---------------------------------------------------------------------- *
   * 文件上传
   * ---------------------------------------------------------------------- */

  const dz = $("#dropzone");
  const fileInput = $("#fileInput");
  const dzTitle = $("#dzTitle");

  fileInput.addEventListener("change", (e) => {
    const f = e.target.files && e.target.files[0];
    if (f) setDebugFile(f);
  });

  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      dz.classList.add("is-drag");
    })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => {
      e.preventDefault();
      dz.classList.remove("is-drag");
    })
  );
  dz.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) setDebugFile(f);
  });

  const setDebugFile = (f) => {
    state.debugFile = f;
    state.debugFileName = f.name;
    dzTitle.textContent = f.name;
  };

  $("#btnUpload").addEventListener("click", async () => {
    if (!state.debugFile) { toast.warn("请先选择文件"); return; }
    const btn = $("#btnUpload");
    btn.disabled = true;
    setResp("// 上传中…", null);
    const t0 = performance.now();
    try {
      const fd = new FormData();
      fd.append("document", state.debugFile);
      const cap = $("#caption").value.trim();
      if (cap) fd.append("caption", cap);
      const r = await fetch("/bot/sendDocument/upload", { method: "POST", body: fd });
      const data = await r.json().catch(() => null);
      const ms = Math.round(performance.now() - t0);
      setResp(fmt.json(data ?? `HTTP ${r.status}`), ms);
      if (r.ok) toast.success("上传完成");
    } catch (e) {
      setResp("UPLOAD ERROR: " + e.message, null);
      toast.error("上传失败");
    } finally {
      btn.disabled = false;
    }
  });

  /* ---------------------------------------------------------------------- *
   * 文件存储
   * ---------------------------------------------------------------------- */

  const renderFiles = () => {
    const tbody = $("#fileTbody");
    if (!state.files.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="5">暂无文件</td></tr>`;
      return;
    }
    tbody.innerHTML = state.files.map((f) => `
      <tr>
        <td title="${escapeHtml(f.path || f.original_name || "")}">${escapeHtml(f.original_name || f.name || "--")}</td>
        <td class="col-num">${escapeHtml(fmt.size(f.size))}</td>
        <td class="col-time">${escapeHtml(fmt.time(f.created_at || f.modified))}</td>
        <td class="col-state"><span class="badge ${f.status === "downloaded" ? "online" : "warn"}">${escapeHtml(f.status || "queued")}</span></td>
        <td class="col-action">
          <button class="icon-btn" data-act="del" data-id="${escapeHtml(f.id || f.msg_id)}" title="删除">
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M11 1.75V3h2.25a.75.75 0 0 1 0 1.5H13.5v9.25A2.25 2.25 0 0 1 11.25 16h-6.5A2.25 2.25 0 0 1 2.5 13.75V4.5h-.25a.75.75 0 0 1 0-1.5H5v-1.25A1.75 1.75 0 0 1 6.75 0h2.5A1.75 1.75 0 0 1 11 1.75Zm-5 0V3h4v-1.25a.25.25 0 0 0-.25-.25h-3.5a.25.25 0 0 0-.25.25ZM6.5 6.5a.75.75 0 0 0-.75.75v5a.75.75 0 0 0 1.5 0v-5a.75.75 0 0 0-.75-.75Zm3 0a.75.75 0 0 0-.75.75v5a.75.75 0 0 0 1.5 0v-5a.75.75 0 0 0-.75-.75Z"/></svg>
          </button>
        </td>
      </tr>
    `).join("");
  };

  $("#fileTbody").addEventListener("click", async (e) => {
    const btn = e.target.closest('[data-act="del"]');
    if (!btn) return;
    const id = btn.dataset.id;
    modal.open({
      title: "删除文件",
      content: `<p>确认删除该文件元数据及物理文件？</p>
                <p style="color:var(--fg-muted);font-size:12px;">ID: ${escapeHtml(id)}</p>`,
      actions: [
        { label: "取消", variant: "btn", onClick: ({ close }) => close() },
        {
          label: "删除", variant: "btn-danger",
          onClick: async ({ close }) => {
            close();
            try {
              await http.del(`/files/${id}`);
              toast.success("文件已删除");
              loadFiles();
            } catch (e) { toast.error("删除失败：" + e.message); }
          },
        },
      ],
    });
  });

  $("#btnCleanup").addEventListener("click", () => {
    modal.open({
      title: "清理过期文件",
      content: `<p>确认清理 30 天前的过期文件？此操作不可撤销。</p>`,
      actions: [
        { label: "取消", variant: "btn", onClick: ({ close }) => close() },
        {
          label: "清理", variant: "btn-danger",
          onClick: async ({ close }) => {
            close();
            try {
              await http.post("/files/cleanup?days=30");
              toast.success("清理任务已提交");
              loadFiles();
            } catch (e) { toast.error("清理失败：" + e.message); }
          },
        },
      ],
    });
  });

  /* ---------------------------------------------------------------------- *
   * 任务 / 插件
   * ---------------------------------------------------------------------- */

  const renderTasks = () => {
    const list = $("#taskList");
    if (!state.tasks.length) {
      list.innerHTML = `<li class="empty-row">暂无定时任务</li>`;
      return;
    }
    list.innerHTML = state.tasks.map((t) => `
      <li>
        <span class="task-time">${escapeHtml(t.time_hm || "")}</span>
        <div class="task-body">
          <div class="task-cmd">${escapeHtml(t.command_text || t.command || "")}</div>
          <div class="task-desc">${escapeHtml(t.description || "无描述")}</div>
        </div>
        <div class="task-actions">
          <button class="toggle ${t.enabled ? "is-on" : ""}" data-act="toggle" data-id="${escapeHtml(t.id)}" title="启用 / 停用"></button>
          <button class="btn btn-sm btn-quiet" data-act="run" data-id="${escapeHtml(t.id)}">执行</button>
          <button class="icon-btn" data-act="del" data-id="${escapeHtml(t.id)}" title="删除">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"/></svg>
          </button>
        </div>
      </li>
    `).join("");
  };

  $("#taskList").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const act = btn.dataset.act;
    if (act === "toggle") {
      const t = state.tasks.find((x) => String(x.id) === String(id));
      try {
        await http.post(`/framework/tasks/${id}/enabled`, { enabled: !t.enabled });
        await loadTasks();
      } catch (e) { toast.error("切换失败"); }
    } else if (act === "run") {
      try { await http.post(`/framework/tasks/${id}/run`); toast.info("已触发手动执行"); }
      catch (e) { toast.error("执行失败"); }
    } else if (act === "del") {
      modal.open({
        title: "删除任务",
        content: `<p>确认删除该定时任务？</p>`,
        actions: [
          { label: "取消", variant: "btn", onClick: ({ close }) => close() },
          {
            label: "删除", variant: "btn-danger",
            onClick: async ({ close }) => {
              close();
              try { await http.del(`/framework/tasks/${id}`); await loadTasks(); toast.success("已删除"); }
              catch (e) { toast.error("删除失败"); }
            },
          },
        ],
      });
    }
  });

  $("#btnNewTask").addEventListener("click", () => openTaskModal());

  const openTaskModal = (initial = {}) => {
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="form-row">
        <label class="form-label" for="t-time">执行时间 (HH:MM)</label>
        <input type="text" id="t-time" class="input" placeholder="08:30" value="${escapeHtml(initial.time || "")}" />
      </div>
      <div class="form-row">
        <label class="form-label" for="t-cmd">执行命令</label>
        <input type="text" id="t-cmd" class="input" placeholder="/status" value="${escapeHtml(initial.command || "")}" />
      </div>
      <div class="form-row">
        <label class="form-label" for="t-desc">任务描述</label>
        <input type="text" id="t-desc" class="input" placeholder="每日早报" value="${escapeHtml(initial.desc || "")}" />
      </div>
    `;
    modal.open({
      title: "新建定时任务",
      content: wrap,
      actions: [
        { label: "取消", variant: "btn", onClick: ({ close }) => close() },
        {
          label: "保存", variant: "btn-primary",
          onClick: async ({ close }) => {
            const time = wrap.querySelector("#t-time").value.trim();
            const cmd  = wrap.querySelector("#t-cmd").value.trim();
            const desc = wrap.querySelector("#t-desc").value.trim();
            if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) { toast.warn("时间格式需为 HH:MM"); return; }
            if (!cmd) { toast.warn("命令不能为空"); return; }
            try {
              await http.post("/framework/tasks", { time_hm: time, command: cmd, description: desc });
              close();
              await loadTasks();
              toast.success("已添加");
            } catch (e) { toast.error("添加失败：" + e.message); }
          },
        },
      ],
    });
  };

  const renderPlugins = () => {
    const list = $("#pluginList");
    if (!state.plugins.length) {
      list.innerHTML = `<li class="empty-row" style="grid-column:1/-1">暂无插件</li>`;
      return;
    }
    list.innerHTML = state.plugins.map((p) => {
      const name = typeof p === "string" ? p : (p.name || p.id || JSON.stringify(p));
      return `<li title="${escapeHtml(name)}">${escapeHtml(name)}</li>`;
    }).join("");
  };

  /* ---------------------------------------------------------------------- *
   * Trace
   * ---------------------------------------------------------------------- */

  const renderTraces = () => {
    const list = $("#traceStream");
    if (!state.traces.length) {
      list.innerHTML = `<div class="empty-row">暂无记录，请确认已开启 WECHAT_TRACE_ENABLED</div>`;
      return;
    }
    list.innerHTML = state.traces.map((t) => {
      const status = (t.status_code || 0) < 400 ? "ok" : (t.status_code < 500 ? "warn" : "error");
      const req = t.request_body_preview ? `<div class="trace-body">REQ: ${escapeHtml(t.request_body_preview)}</div>` : "";
      const res = t.response_body_preview ? `<div class="trace-body">RES: ${escapeHtml(t.response_body_preview)}</div>` : "";
      return `
        <div class="trace-card">
          <div class="trace-head">
            <span class="trace-method ${escapeHtml(t.method || "GET")}">${escapeHtml(t.method || "GET")}</span>
            <span class="trace-url" title="${escapeHtml(t.url || "")}">${escapeHtml(t.url || "")}</span>
            <span class="trace-status ${status}">${escapeHtml(String(t.status_code || "?"))}</span>
          </div>
          ${req}${res}
          <div class="trace-time">${escapeHtml(fmt.time((t.timestamp || 0) * 1000))}</div>
        </div>
      `;
    }).join("");
  };

  $("#btnClearTrace").addEventListener("click", async () => {
    try {
      await http.post("/trace/clear", {});
      state.traces = [];
      renderTraces();
      toast.success("追踪记录已清空");
    } catch (e) { toast.error("清空失败"); }
  });

  $("#btnRefreshTrace").addEventListener("click", () => loadTraces());

  /* ---------------------------------------------------------------------- *
   * 消息详情
   * ---------------------------------------------------------------------- */

  const showMsgDetail = (msg) => {
    const wrap = document.createElement("div");
    wrap.innerHTML = `
      <div class="detail-grid">
        <div class="detail-key">Message ID</div>
        <div class="detail-val">${escapeHtml(msg.id || "")}</div>
        <div class="detail-key">类型</div>
        <div class="detail-val"><span class="badge ${escapeHtml(msg.type || "")}">${escapeHtml(msg.type || "")}</span></div>
        <div class="detail-key">时间</div>
        <div class="detail-val">${escapeHtml(fmt.time(msg.created_at))}</div>
        <div class="detail-key">文本内容</div>
        <div class="detail-val is-text">${escapeHtml(msg.text || "无")}</div>
        <div class="detail-key">Extra</div>
        <div class="detail-val">${escapeHtml(fmt.json(msg.extra || {}))}</div>
      </div>
    `;
    modal.open({
      title: "消息详情",
      content: wrap,
      actions: [{ label: "关闭", variant: "btn", onClick: ({ close }) => close() }],
    });
  };

  /* ---------------------------------------------------------------------- *
   * 数据加载
   * ---------------------------------------------------------------------- */

  async function pollStatus() {
    try {
      const r = await http.get("/webui/status");
      state.status = r.data;
      // 未登录且还没有二维码时，拉一张
      if (!state.status.logged_in && !state.qrBase64) {
        refreshQr();
      } else if (state.status.logged_in) {
        state.qrBase64 = null;
      }
      renderStatus();
      renderStats();
    } catch (e) {
      const pill = $("#connPill");
      pill.dataset.state = "offline";
      pill.querySelector(".status-text").textContent = "连接失败";
    }
  }

  async function refreshQr() {
    try {
      const r = await http.get("/webui/qr");
      state.qrBase64 = r.data && r.data.qr_base64;
      renderStats();
    } catch (e) {
      toast.error("获取二维码失败");
    }
  }

  async function refreshStats() {
    try {
      const r = await http.get("/store/stats");
      state.stats = r.data || {};
      renderStats();
    } catch {}
  }

  async function loadMessages(append = false) {
    try {
      if (!append) state.msgOffset = 0;
      const params = new URLSearchParams({
        limit: "20",
        offset: String(state.msgOffset),
      });
      if (state.msgType) params.set("msg_type", state.msgType);
      const r = await http.get(`/store/messages?${params.toString()}`);
      const list = (r.data && (r.data.messages || r.data)) || [];
      if (append) {
        state.messages = [...state.messages, ...list];
        state.msgOffset += list.length || 20;
      } else {
        state.messages = list;
        state.msgOffset = list.length || 20;
      }
      renderMessages();
    } catch (e) { toast.error("加载消息失败"); }
  }

  async function loadFiles() {
    try {
      const r = await http.get("/files/metadata?limit=50");
      state.files = (r.data && (r.data.files || r.data)) || [];
      renderFiles();
    } catch (e) { toast.error("加载文件失败"); }
  }

  async function loadTasks() {
    try {
      const r = await http.get("/framework/tasks");
      state.tasks = (r.data && (r.data.tasks || [])) || [];
      renderTasks();
    } catch {}
  }

  async function loadPlugins() {
    try {
      const r = await http.get("/plugins");
      const raw = r.data;
      if (Array.isArray(raw)) state.plugins = raw;
      else if (raw && Array.isArray(raw.plugins)) state.plugins = raw.plugins;
      else if (raw && Array.isArray(raw.loaded)) state.plugins = raw.loaded;
      else state.plugins = [];
      renderPlugins();
    } catch {}
  }

  async function loadTraces() {
    try {
      const r = await http.get("/trace/recent?limit=100");
      state.traces = (r.data && (r.data.traces || r.data)) || [];
      renderTraces();
    } catch {}
  }

  async function executeCommand(cmd) {
    try {
      const r = await http.post("/framework/execute", { command: cmd, send_back: true });
      const text = (r.data && r.data.result) || "已执行";
      toast.info("执行成功：" + (typeof text === "string" ? text.slice(0, 60) : ""));
    } catch (e) { toast.error("执行失败"); }
  }

  async function refreshAll() {
    await Promise.all([pollStatus(), refreshStats()]);
    await loadTabData();
  }

  async function loadTabData() {
    switch (state.tab) {
      case "messages":  await loadMessages(false); break;
      case "files":     await loadFiles(); break;
      case "framework": await Promise.all([loadTasks(), loadPlugins()]); break;
      case "trace":     await loadTraces(); break;
    }
  }

  /* ---------------------------------------------------------------------- *
   * 启动
   * ---------------------------------------------------------------------- */

  renderEndpoints();
  state.debug.payload = fmt.json(ENDPOINTS[0].defaults);
  $("#payload").value = state.debug.payload;

  refreshAll();
  setInterval(pollStatus, 3000);
  setInterval(refreshStats, 15000);
})();