// homeboard UI: renders status.json (written by the collector) every minute.
const FLUENT = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@1ffb34c752ecf5d402f04cfb4b392c77f57c54bc/assets";
const F = n => `${FLUENT}/${encodeURIComponent(n)}/3D/${n.toLowerCase().replace(/ /g, "_")}_3d.png`;
const W = 1200, H = 860, pct = (x, y) => `left:${x / W * 100}%;top:${y / H * 100}%`;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let T = {};
const t = k => T[k] ?? k;

const CLOUD_SLOTS = [[115, 150], [300, 84], [440, 212], [760, 212], [900, 84], [1085, 150], [600, 56]];
const NET = [600, 196], ROUTER = [600, 486], SERVER_TOP = [600, 640];

const fmt = {
  pct: v => v == null ? "—" : `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`,
  brl: v => v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" }),
  usd: v => v == null ? "—" : `US$ ${v.toFixed(2)}`,
  bytes: v => { if (v == null) return "—"; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; while (v >= 1000 && i < 4) { v /= 1000; i++; } return `${v.toFixed(i > 2 ? 1 : 0)} ${u[i]}`; },
};

const rows = r => r.filter(Boolean).map(([k, v]) => `<div class="r"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join("");
const bars = daily => daily ? `<div class="ub">${daily.map(v => `<i class="${v == null ? "" : v < 99 ? (v < 90 ? "b" : "w") : ""}" style="${v == null ? "opacity:.15" : ""}"></i>`).join("")}</div>` : "";
const tip = (title, r, o = {}) => `<div class="tip${o.below ? " below" : ""}" style="--c:${o.c || "var(--line2)"}"><h5>${esc(title)}</h5>${rows(r)}${bars(o.daily)}${o.note ? `<p>${esc(o.note)}</p>` : ""}</div>`;
const block = (s, name) => s.blocks?.[name]?.ok ? s.blocks[name].data : null;

function serviceState(s, svc) {
  const [kind, key] = (svc.status || "").split(":");
  if (kind === "uplink") {
    const r = block(s, "router");
    if (r) return { up: r.uplinks[key], active: r.active === key, hist: s.history?.[svc.status] };
  }
  if (kind === "page") {
    const p = block(s, "status_pages")?.[key];
    if (p) return { up: p.up !== false, active: svc.role !== "standby", degraded: p.degraded, desc: p.description, hist: s.history?.[svc.status] };
  }
  if (kind === "app") {
    const p = block(s, "probes")?.[key];
    if (p) return { up: p.ok, active: svc.role !== "standby", ms: p.ms, hist: s.history?.[svc.status] };
  }
  return { up: true, active: svc.role !== "standby" };
}

function card(s, category, [x, y], color, wide) {
  const items = s.catalog.categories[category] || [];
  if (!items.length) return "";
  const below = y < 260;
  return `<div class="svc${wide ? " wide" : ""}" style="${pct(x, y)};--c:${color}"><div class="svh"><img src="${F(items[0].icon || "Sparkles")}" alt=""><b>${esc(t("cat_" + category))}</b></div>
   <div class="svi">${items.map(svc => {
     const st = serviceState(s, svc), off = !st.active;
     const r = block(s, "router");
     const extra = svc.status?.startsWith("uplink:") && r ? [
       st.active && r.rate_mbps && [t("speed_now"), `${r.rate_mbps.down} ↓ / ${r.rate_mbps.up} ↑ Mbps`],
       svc.status === "uplink:5g" && r.modem?.rsrp != null && [t("signal"), `${r.modem.rsrp} dBm · ${r.modem.type || ""}`],
     ] : [];
     const flow = s.service_traffic?.[svc.name];
     const tr = [[off ? t("standby") : t("active"), st.up === false ? t("down") : t("up")],
       flow && ["↓", mbpsText(flow.down_mbps)], flow && ["↑", mbpsText(flow.up_mbps)],
       st.hist && [t("uptime30"), fmt.pct(st.hist.uptime_pct)], st.hist && [t("downtime"), `${st.hist.downtime_min} ${t("minutes")}`],
       st.ms != null && [t("latency"), `${st.ms} ms`], st.desc && [t("status_page"), st.desc], ...extra, svc.monthly_brl != null && [t("costs"), fmt.brl(svc.monthly_brl)], svc.note && ["", svc.note]];
     return `<div class="si${off ? " off" : ""}" data-svc="${esc(svc.name)}"><img src="${F(svc.icon || "Sparkles")}" alt=""><b>${esc(svc.name)}</b><small>${flow && both(flow) >= 0.05 ? `↓ ${mbpsText(flow.down_mbps)}` : esc(st.up === false ? t("down") : st.degraded ? t("degraded") : off ? t("standby") : t("active"))}</small>
       ${tip(svc.name, tr, { c: off ? "var(--line2)" : color, below, daily: st.hist?.daily })}</div>`;
   }).join("")}</div></div>`;
}

function node([x, y], icon, label, sub, tipHtml, color) {
  return `<div class="node" style="${pct(x, y)};--s:${icon === "Globe with meridians" ? 86 : 72}px;--g:${color}88"><div class="bubwrap"><div class="bub"><img src="${F(icon)}" alt=""></div><i class="status"></i></div>
   <b>${esc(label)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}${tipHtml}</div>`;
}

function group(side, title, sub, icon, items, color) {
  return `<div class="group ${side}" style="--c:${color}"><div class="gtop"><img src="${F(icon)}" alt=""><div><b>${esc(title)}</b><small>${esc(sub)}</small></div></div>
   <div class="gitems">${items.map(d => `<div class="gi${d.online ? "" : " off"}"><i class="status${d.online ? "" : " off"}"></i><img src="${F(d.icon || "Desktop computer")}" alt=""><b>${esc(d.name)}</b>
     <small>${!d.online ? t("offline") : both(d) >= 0.05 ? `↓ ${mbpsText(d.down_mbps)}` : t("online")}</small>
     ${tip(d.name, [[t("online"), d.online ? "✓" : "—"], d.down_mbps != null && ["↓", mbpsText(d.down_mbps)], d.up_mbps != null && ["↑", mbpsText(d.up_mbps)]], { c: color })}</div>`).join("")}</div></div>`;
}

// Packets move faster with more traffic and stop when the link is idle.
function speed(mbps) {
  if (mbps == null) return "";
  if (mbps < 0.02) return "animation-play-state:paused;opacity:.25";
  return `animation-duration:${Math.max(0.25, 3 - Math.log10(1 + mbps) * 1.1).toFixed(2)}s`;
}

function curve([x1, y1], [x2, y2], cls, stroke, mbps) {
  const my = (y1 + y2) / 2;
  return `<path class="ln ${cls}" ${stroke ? `stroke="${stroke}"` : ""} style="${speed(mbps)}" d="M${x1} ${y1} C${x1} ${my} ${x2} ${my} ${x2} ${y2}"/>`;
}

const mbpsText = v => v == null ? "—" : v >= 10 ? `${v.toFixed(0)} Mbps` : v >= 0.1 ? `${v.toFixed(1)} Mbps` : `${Math.round(v * 1000)} kbps`;
const both = r => r ? (r.down_mbps || 0) + (r.up_mbps || 0) : null;

function renderMap(s) {
  const m = s.map || {}, cloud = m.cloud || [], domain = s.site.domain;
  const colors = ["#5ee8b0", "#86b6ff", "#f1f2f8", "#a99bff", "#ffd36b", "#ff8a8a", "#ffb38a"];
  const r = block(s, "router"), srv = block(s, "server");
  let html = "", links = "";
  cloud.forEach((cat, i) => {
    const slot = CLOUD_SLOTS[i % CLOUD_SLOTS.length];
    html += card(s, cat, slot, colors[i % colors.length]);
    links += curve(NET, [slot[0], slot[1] + 28], "cloud");
    const catFlow = (s.catalog.categories[cat] || []).reduce((x, svc) => x + (both(s.service_traffic?.[svc.name]) || 0), 0);
    if (catFlow > 0) links += curve(NET, [slot[0], slot[1] + 28], "flow", colors[i % colors.length], catFlow);
  });
  html += node(NET, "Globe with meridians", t("internet"), r?.active || "", tip(t("internet"), [[t("active"), r?.active || "—"]], { c: "#7fdcff" }), "#7fdcff");
  if (m.center) html += card(s, m.center, [600, 336], "#7fdcff", true);
  if (m.left) { html += card(s, m.left, [255, 330], "#ffb38a"); links += curve(ROUTER, [315, 360], "wifi"); }
  if (m.right) { html += card(s, m.right, [945, 330], "#5ee8b0"); links += curve(ROUTER, [885, 360], "wifi"); }
  const rtip = r ? tip(t("router"), [[t("active"), r.active || "—"], r.rate_mbps && [t("speed_now"), `${r.rate_mbps.down} ↓ / ${r.rate_mbps.up} ↑ Mbps`],
    [t("wifi_clients"), r.wifi_clients], [t("vpn_peers"), `${r.vpn.active}/${r.vpn.peers}`]], { c: "#7fdcff" }) : tip(t("router"), [[t("unavailable"), "—"]]);
  html += node(ROUTER, "Satellite antenna", t("router"), "", rtip, "#7fdcff");
  const wan = r?.rate_mbps ? r.rate_mbps.down + r.rate_mbps.up : null;
  const dev0 = s.devices || {}, gt = dev0.traffic || {};
  links += curve(NET, [548, 348], "base") + curve(NET, [548, 348], "flow", "#7fdcff", wan) + curve(NET, [652, 348], "standby");
  links += curve([548, 348], ROUTER, "base") + curve([548, 348], ROUTER, "flow", "#7fdcff", wan) + curve([652, 348], ROUTER, "standby");
  links += curve(ROUTER, SERVER_TOP, "base") + curve(ROUTER, SERVER_TOP, "flow", "#5ee8b0", both(s.server_traffic));
  links += curve(ROUTER, [300, 600], "wifi") + curve(ROUTER, [900, 600], "wifi");
  links += curve(ROUTER, [300, 600], "flow", "#86b6ff", both(gt.personal)) + curve(ROUTER, [900, 600], "flow", "#ff9ccf", both(gt.iot));
  if (r?.rate_mbps) html += `<div class="pill" style="${pct(505, 262)};--c:#7fdcff">${r.rate_mbps.down} Mbps${tip(t("speed_now"), [["↓", `${r.rate_mbps.down} Mbps`], ["↑", `${r.rate_mbps.up} Mbps`]], { c: "#7fdcff" })}</div>`;
  const dev = s.devices || { personal: [], iot: [] };
  const gpill = (g, x, color, title) => {
    const on = dev[g].filter(d => d.online).length, tr = gt[g];
    return `<div class="pill" style="${pct(x, 548)};--c:${color}">${title} · ${tr && both(tr) >= 0.05 ? mbpsText(both(tr)) : on}${tip(title, [[t("online"), `${on}/${dev[g].length}`],
      tr && ["↓", mbpsText(tr.down_mbps)], tr && ["↑", mbpsText(tr.up_mbps)]], { c: color })}</div>`;
  };
  html += gpill("personal", 372, "#86b6ff", t("personal")) + gpill("iot", 828, "#ff9ccf", "IoT");
  if (s.server_traffic) html += `<div class="pill" style="${pct(600, 556)};--c:#5ee8b0">${mbpsText(both(s.server_traffic))}${tip(t("server"), [["↓", mbpsText(s.server_traffic.down_mbps)], ["↑", mbpsText(s.server_traffic.up_mbps)]], { c: "#5ee8b0" })}</div>`;
  html += group("left", t("personal"), t("personal_sub"), "Busts in silhouette", dev.personal, "#86b6ff");
  html += group("right", t("iot"), t("iot_sub"), "Light bulb", dev.iot, "#ff9ccf");
  const vit = srv ? `<span>CPU <b>${srv.cpu_pct ?? "—"}%</b></span><span>${srv.cpu_temp_c ?? "—"} <b>°C</b></span><span>RAM <b>${fmt.bytes(srv.memory.used_bytes)}</b></span>` : `<span>${t("unavailable")}</span>`;
  const bk = block(s, "backup");
  html += `<div class="server"><div class="top"><img src="${F("Card file box")}" alt=""><div><b>${t("server")}</b><small>${(s.apps || []).length} apps</small></div>
    <div class="vit">${vit}${bk ? `<span>${t("backup")} <b>${bk.ok && !bk.stale ? "ok" : t("attention")}</b></span>` : ""}</div></div>
    <div class="apps">${(s.apps || []).map(a => `<a class="app${a.state === "paused" ? " paused" : ""}" data-app="${esc(a.label)}" href="#">
      <i class="status${a.state === "up" ? "" : a.state === "paused" ? " off" : " warn"}"></i><img src="${F(a.icon || "Gear")}" alt=""><b>${esc(a.label)}</b>
      ${tip(a.label, [[t(a.state), a.ms != null ? `${a.ms} ms` : ""], s.history?.[`app:${a.host}`] && [t("uptime30"), fmt.pct(s.history[`app:${a.host}`].uptime_pct)]], { daily: s.history?.[`app:${a.host}`]?.daily })}</a>`).join("")}</div></div>`;
  html += caio(s);
  const stage = $("stage");
  stage.querySelectorAll(".node,.svc,.pill,.group,.server,.caio").forEach(e => e.remove());
  stage.insertAdjacentHTML("beforeend", html);
  $("links").innerHTML = links;
}

function renderStrip(s) {
  const r = block(s, "router"), bk = block(s, "backup"), dns = block(s, "dns"), ai = block(s, "ai_spend");
  const apps = s.apps || [], up = apps.filter(a => a.state !== "down").length;
  const chips = [
    ["Sparkles", `${t("all_ok")} <b>${up}/${apps.length}</b>`, up === apps.length ? "" : "warn"],
    r && ["Globe with meridians", `${t("internet")} <b>${esc(r.active || t("down"))}</b>`, r.active ? "" : "warn"],
    bk && ["Floppy disk", `${t("backup")} <b>${bk.ok && !bk.stale ? `${bk.age_hours} ${t("hours_ago")}` : t("stale")}</b>`, bk.ok && !bk.stale ? "" : "warn"],
    dns && ["Shield", `DNS <b>${fmt.pct(dns.blocked_pct)}</b>`, ""],
    ai && ["Coin", `${t("ai_usage")} <b>${fmt.usd(ai.month_usd)}</b>`, ""],
  ].filter(Boolean);
  $("strip").innerHTML = chips.map(([ic, txt, cls]) => `<div class="chip"><img src="${F(ic)}" alt=""><i class="dot ${cls}"></i>${txt}</div>`).join("");
}

// A source that is not configured hides its section; a configured one that fails shows "unavailable".
function section(id, s, name) {
  const show = name in (s.blocks || {});
  $(id).style.display = show ? "" : "none";
  $(id).previousElementSibling.style.display = show ? "" : "none";
  return show;
}

const unavailable = (icon, title) => `<div class="card"><div class="hd"><img src="${F(icon)}" alt=""><h2>${esc(title)}</h2></div><div class="unavail">${t("unavailable")}</div></div>`;

function renderStorage(s) {
  if (!section("storage", s, "server")) return;
  const srv = block(s, "server"), bk = block(s, "backup");
  if (!srv) { $("storage").innerHTML = unavailable("Herb", t("health")); return; }
  const disks = srv.disks, healthy = disks.every(d => d.healthy) && srv.array.disabled === 0;
  const temps = disks.map(d => `<div class="t"><b>${d.temp_c ?? "—"}°</b><span>${esc(d.name)}</span></div>`).join("") + `<div class="t"><b>${srv.cpu_temp_c ?? "—"}°</b><span>CPU</span></div>`;
  const used = d => d.size_bytes ? `${fmt.bytes(d.used_bytes)} / ${fmt.bytes(d.size_bytes)}` : "—";
  $("storage").innerHTML = `
   <div class="card"><div class="hd"><img src="${F("Herb")}" alt=""><h2>${t("health")}</h2></div><div class="body">
     <div class="big" style="color:${healthy ? "var(--ok)" : "var(--warn)"}">${t(healthy ? "healthy" : "attention")}</div>
     <div class="line"><span>${t("disks")}</span><b>${disks.filter(d => d.healthy).length} / ${disks.length}</b></div>
     <div class="line"><span>${t("parity")}</span><b>${srv.array.parity_errors === 0 ? t("valid") : `${srv.array.parity_errors} ${t("errors")}`}</b></div></div></div>
   <div class="card"><div class="hd"><img src="${F("Thermometer")}" alt=""><h2>${t("temperature")}</h2><span>°C</span></div><div class="body"><div class="temps">${temps}</div></div></div>
   ${bk ? `<div class="card"><div class="hd"><img src="${F("Floppy disk")}" alt=""><h2>${t("backup")}</h2></div><div class="body">
     <div class="line"><span>${t("last_copy")}</span><b style="color:${bk.ok && !bk.stale ? "var(--text)" : "var(--warn)"}">${bk.age_hours} ${t("hours_ago")}${bk.seconds ? ` · ${Math.round(bk.seconds / 60)} ${t("minutes")}` : ""}</b></div>
     ${bk.error ? `<div class="line"><span>erro</span><b style="color:var(--bad)">${esc(bk.error)}</b></div>` : ""}</div></div>` : unavailable("Floppy disk", t("backup"))}
   <div class="card"><div class="hd"><img src="${F("Package")}" alt=""><h2>${t("space")}</h2></div><div class="dlist">
     ${disks.map(d => `<div class="r"><span>${esc(d.name)} · ${d.rotational ? (d.spinning ? t("spinning") : t("stopped")) : "SSD"}</span><b class="mono">${used(d)}</b></div>`).join("")}</div></div>`;
}

const SOURCE_ICON = { whatsapp: "Speech balloon", cron: "Hourglass not done", cli: "Desktop computer", tui: "Desktop computer", api_server: "Link", subagent: "Robot" };
const ago = m => m < 60 ? `${m} min` : m < 1440 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} d`;
const hhmm = ts => new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
const brlFromUsd = (s, usd) => s.costs?.fx && usd != null ? fmt.brl(usd * s.costs.fx.usd_brl) : fmt.usd(usd);

// ---------- details popup (every app and service) ----------
let MODAL = null, LAST = null;
const fact = (k, v) => v == null || v === "" ? "" : `<div class="fact"><span>${esc(k)}</span><b>${v}</b></div>`;
const bigBars = daily => daily ? `<div class="ub big">${daily.map(v => `<i class="${v == null ? "" : v < 99 ? (v < 90 ? "b" : "w") : ""}" style="${v == null ? "opacity:.15" : ""}" title="${v == null ? "" : v + "%"}"></i>`).join("")}</div>` : "";

function consoleUrl(s, item) {
  if (item.console) return item.console;
  return item.host && s.site.domain ? `https://${item.host}.${s.site.domain}` : null;
}

function agentPanel(s) {
  const act = s.agent_activity, b = s.agent_budget, a = block(s, "agent");
  if (!act) return "";
  const n = act.now, h = act.health, name = s.agent_name || "Hermes";
  const access = {};
  act.diary.forEach(d => access[d.source] = (access[d.source] || 0) + 1);
  const pct = b?.max_usd ? Math.min(100, 100 * b.spend_usd / b.max_usd) : 0;
  const today = act.diary.filter(d => new Date(d.first * 1000).toDateString() === new Date().toDateString()).reduce((x, d) => x + (d.cost_usd || 0), 0);
  return `
   <div class="msec"><h4>${esc(name)}</h4><p class="lead">${n?.active ? `${t("task_" + n.task)} · ${ago(n.minutes)}` : `${t("idle")} · ${t("last_task")} ${ago(n?.idle_minutes ?? 0)}`}</p></div>
   <div class="mgrid">
     <div class="msec"><h4>${t("tasks")}</h4><div class="dlist diary">${act.diary.map(d => `<div class="r">
       <span class="dtitle"><img src="${F(SOURCE_ICON[d.source] || "Gear")}" alt="">${esc(t("task_" + d.task))}<em class="mono"> ${esc((d.title || "").slice(0, 60))}</em></span>
       <span class="mono dmeta">${hhmm(d.first)} · ${ago(d.minutes)}${d.errors ? ` · <em class="bad">${d.errors} ${t("errors_short")}</em>` : ""}</span>
       <b class="mono">${d.cost_usd ? brlFromUsd(s, d.cost_usd) : "—"}</b></div>`).join("")}</div></div>
     <div>
       <div class="msec"><h4>${t("cost_eff")}</h4>
         ${b ? fact(`${t("budget")} (${b.duration || ""})`, `${brlFromUsd(s, b.spend_usd)} / ${brlFromUsd(s, b.max_usd)}`) + `<div class="prog"><i style="width:${pct}%;background:linear-gradient(90deg,#5ee8b0,${pct > 80 ? "#ff8a8a" : "#ffd36b"})"></i></div>` : ""}
         ${fact(t("cost_today"), brlFromUsd(s, today))}${fact(t("cache_pct"), h.cache_pct != null ? h.cache_pct + "%" : "—")}
         ${Object.entries(a?.tiers || {}).map(([k, v]) => fact(k, `<span class="mono small">${esc(v)}</span>`)).join("")}</div>
       <div class="msec"><h4>${t("access")}</h4>${Object.entries(access).map(([k, v]) => fact(k, `${v} ${t("tasks_short")}`)).join("")}</div>
       <div class="msec"><h4>${t("agent_health")}</h4>${fact(t("tool_calls"), h.tool_calls_today)}${fact(t("errors"), `${h.tool_errors_today}`)}
         ${h.errors_by_tool.map(([k, v]) => fact(k, v)).join("")}</div>
     </div>
   </div>
   <div class="msec"><h4>${t("changes")}</h4><div class="dlist">${act.changes.map(c => `<div class="r"><span class="mono small">${c.kind === "file" ? "✎" : "›"} ${esc(c.text)}</span><b class="mono small">${new Date(c.time * 1000).toLocaleString(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</b></div>`).join("") || `<div class="r"><span>${t("no_changes")}</span></div>`}</div></div>`;
}

function appModal(s, app) {
  const hist = s.history?.[`app:${app.host}`], st = block(s, "container_stats")?.[app.container];
  const agent = s.agent_activity && app.container && app.container === (s.map?.agent_container || "hermes");
  const url = consoleUrl(s, app);
  return `<div class="mhead"><img src="${F(app.icon || "Gear")}" alt=""><div><h3>${esc(app.label)}</h3><small>${esc(app.container || app.host || "")}</small></div>
      <span class="badge-state ${app.state}">${t(app.state)}</span>${url ? `<a class="btn" href="${url}" target="_blank" rel="noopener">${t("open_console")} ↗</a>` : ""}</div>
    <div class="facts">${fact(t("uptime30"), hist ? fmt.pct(hist.uptime_pct) : null)}${fact(t("downtime"), hist ? `${hist.downtime_min} ${t("minutes")}` : null)}
      ${fact(t("latency"), app.ms != null ? `${app.ms} ms` : null)}${st ? fact("CPU", st.cpu_pct != null ? `${st.cpu_pct}%` : "—") + fact(t("memory"), fmt.bytes(st.mem_bytes)) + fact(t("processes"), st.pids) : ""}</div>
    ${bigBars(hist?.daily)}${agent ? agentPanel(s) : ""}`;
}

function svcModal(s, svc) {
  const st = serviceState(s, svc), flow = s.service_traffic?.[svc.name], hist = st.hist;
  return `<div class="mhead"><img src="${F(svc.icon || "Sparkles")}" alt=""><div><h3>${esc(svc.name)}</h3><small>${esc(t("cat_" + svc.category))}</small></div>
      <span class="badge-state ${st.up === false ? "down" : "up"}">${st.active ? t("active") : t("standby")}</span>${svc.console ? `<a class="btn" href="${svc.console}" target="_blank" rel="noopener">${t("open_console")} ↗</a>` : ""}</div>
    <div class="facts">${fact(t("costs"), svc.monthly_brl != null ? fmt.brl(svc.monthly_brl) : t("missing_cost"))}${fact(t("status_page"), st.desc)}
      ${fact("↓", flow ? mbpsText(flow.down_mbps) : null)}${fact("↑", flow ? mbpsText(flow.up_mbps) : null)}
      ${fact(t("uptime30"), hist ? fmt.pct(hist.uptime_pct) : null)}${fact(t("latency"), st.ms != null ? `${st.ms} ms` : null)}${fact("", svc.note ? esc(svc.note) : null)}</div>${bigBars(hist?.daily)}`;
}

function openModal(kind, key) { MODAL = { kind, key }; drawModal(); $("modal").hidden = false; }
function closeModal() { MODAL = null; $("modal").hidden = true; }
function drawModal() {
  if (!MODAL || !LAST) return;
  const s = LAST;
  if (MODAL.kind === "app") { const app = (s.apps || []).find(a => a.label === MODAL.key); if (app) $("mbody").innerHTML = appModal(s, app); }
  if (MODAL.kind === "svc") { const svc = Object.values(s.catalog.categories).flat().find(x => x.name === MODAL.key); if (svc) $("mbody").innerHTML = svcModal(s, svc); }
}
document.addEventListener("click", e => {
  const app = e.target.closest(".app[data-app]"), svc = e.target.closest(".si[data-svc]"), caio = e.target.closest(".caio");
  if (app) { e.preventDefault(); openModal("app", app.dataset.app); }
  else if (svc) openModal("svc", svc.dataset.svc);
  else if (caio && LAST) { const h = (LAST.apps || []).find(a => a.container === (LAST.map?.agent_container || "hermes")); if (h) openModal("app", h.label); }
  else if (e.target.id === "modal" || e.target.classList.contains("mclose")) closeModal();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// ---------- the agent as a presence on the map ----------
function caio(s) {
  const n = s.agent_activity?.now;
  if (!n) return "";
  const name = s.agent_name || "Hermes";
  return `<div class="caio ${n.active ? "busy" : "idle"}" style="${pct(1125, 335)}" title="${esc(name)}">
    ${n.active ? `<div class="balloon">${esc(t("task_" + n.task))}…</div>` : `<div class="zzz"><i>z</i><i>z</i><i>z</i></div>`}
    <div class="ring"></div><div class="face"><img src="${F("Robot")}" alt=""></div><b>${esc(name)}</b></div>`;
}

function renderCosts(s) {
  const c = s.costs;
  if (!c) return;
  const label = p => p.key === "subscriptions" || p.key === "ai_usage" ? t(p.key) : t("cat_" + p.key) !== "cat_" + p.key ? t("cat_" + p.key) : p.key === "other" ? t("tier_other") : p.key;
  const money = p => p.brl != null ? fmt.brl(p.brl) : `${fmt.usd(p.usd)} · ${t("no_fx")}`;
  const share = p => p.brl != null && c.total_brl ? ` <span class="share">${Math.round(100 * p.brl / c.total_brl)}%</span>` : "";
  $("costs").innerHTML = `
   <div class="card" style="grid-column:span 3"><div class="hd"><img src="${F("Bar chart")}" alt=""><h2>${t("month_total")}</h2>
     <span class="mono">${c.fx ? `US$ 1 = ${fmt.brl(c.fx.usd_brl)} · PTAX ${esc(c.fx.date)}` : t("no_fx")}</span></div>
     <div class="costhead"><div class="big mono">${fmt.brl(c.total_brl)}</div></div>
     <div class="breakdown">${c.parts.map(p => `
       <div class="bpart"><div class="gh"><span>${esc(label(p))}${share(p)}</span><b>${money(p)}</b></div>
         ${p.children.map(ch => `<div class="brow"><span>${esc(label(ch))}${ch.usd != null ? ` <em class="mono">${fmt.usd(ch.usd)}</em>` : ""}</span><b class="mono">${money(ch)}</b></div>
           ${(ch.items || []).map(i => `<div class="brow sub"><span>${esc(i.name)}</span><b class="mono">${fmt.brl(i.brl)}</b></div>`).join("")}`).join("")}
       </div>`).join("")}</div>
     ${c.missing.length ? `<div class="body"><div class="line"><span>${t("missing_cost")}</span><b>${c.missing.map(esc).join(", ")}</b></div></div>` : ""}
   </div>`;
}

async function refresh() {
  try {
    const s = await (await fetch(`status.json?ts=${Date.now()}`)).json();
    if (!Object.keys(T).length) T = await (await fetch(`i18n/${s.site.language || "pt-BR"}.json`)).json();
    document.documentElement.lang = s.site.language || "pt-BR";
    document.title = s.site.name;
    $("site-name").textContent = s.site.name;
    $("site-sub").textContent = s.site.subtitle || "";
    document.querySelectorAll("[data-t]").forEach(e => e.textContent = t(e.dataset.t));
    $("updated").textContent = new Date(s.generated_at).toLocaleTimeString(s.site.language);
    LAST = s;
    renderStrip(s); renderMap(s); renderStorage(s); renderCosts(s); drawModal();
  } catch (e) {
    console.error(e);
  }
}

document.querySelectorAll("img[data-f]").forEach(i => i.src = F(i.dataset.f));
const clock = () => { const d = new Date(); $("hh").textContent = d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }); $("dd").textContent = d.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" }); };
clock(); setInterval(clock, 10000);
refresh(); setInterval(refresh, 10000);
