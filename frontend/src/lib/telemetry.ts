import { registerWebApiTelemetryReporter } from "./apiClient";

export type WebTelemetryEventType =
  | "session_start"
  | "page_enter"
  | "page_leave"
  | "button_click"
  | "modal_open"
  | "modal_close"
  | "funnel_step"
  | "api_issue"
  | "session_end";

export interface WebTelemetryEvent {
  event_id?: string;
  session_id?: string;
  event_type: WebTelemetryEventType;
  event_name: string;
  event_label?: string;
  page_path?: string;
  page_title?: string;
  stay_ms?: number;
  scroll_pct?: number | null;
  client_ts: number;
  props?: Record<string, any>;
}

const WEB_PAGE_TITLES: Record<string, string> = {
  "/": "官网首页",
  "/login": "登录注册",
  "/dashboard": "首页总览 (Web)",
  "/dashboard/coach": "科学训练课表 (Web)",
  "/dashboard/team": "跑团中心 (Web)",
  "/dashboard/cockpit": "教练工作台 (Web)",
  "/dashboard/profile": "我的档案与跑表 (Web)",
  "/dashboard/admin": "超管控制台 (Web)",
  "/manual": "帮助与手册 (Web)",
};

const CLIENT_UUID_KEY = "rgm_web_client_uuid";
const SESSION_TIMEOUT_MS = 15 * 60 * 1000;
const FLUSH_INTERVAL_MS = 8000;

let sessionId = "";
let entryPage = "";
let eventSeq = 0;
let eventQueue: WebTelemetryEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let isFlushing = false;
let initialized = false;
let lastHiddenAt = 0;

let activeRoute = "";
let activeEnteredAt = 0;
let maxScrollPct = 0;

function getOrCreateClientUuid(): string {
  if (typeof window === "undefined") return "ssr";
  try {
    let cid = localStorage.getItem(CLIENT_UUID_KEY);
    if (!cid) {
      cid = "web_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(CLIENT_UUID_KEY, cid);
    }
    return cid;
  } catch {
    return "web_ephemeral";
  }
}

function getAuthTokenForTelemetry(): string {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem("rgm_auth_session");
    if (raw) {
      const parsed = JSON.parse(raw);
      const t = parsed?.access_token || parsed?.token;
      if (t) return String(t);
    }
  } catch {}
  try {
    return localStorage.getItem("rgm_token") || localStorage.getItem("rgm_admin_token") || "";
  } catch {
    return "";
  }
}

function resolvePageTitle(pathname: string): string {
  return WEB_PAGE_TITLES[pathname] || pathname;
}

function sampleScrollPct() {
  if (typeof window === "undefined" || typeof document === "undefined") return;
  const docEl = document.documentElement;
  const scrollHeight = Math.max(docEl.scrollHeight, document.body?.scrollHeight || 0);
  const viewH = window.innerHeight || docEl.clientHeight || 800;
  if (scrollHeight <= viewH + 24) {
    maxScrollPct = Math.max(maxScrollPct, 100);
    return;
  }
  const pct = Math.min(100, Math.max(0, Math.round(((window.scrollY + viewH) / scrollHeight) * 100)));
  if (pct > maxScrollPct) maxScrollPct = pct;
}

function ensureSession(initialPath?: string) {
  if (typeof window === "undefined") return;
  const now = Date.now();
  const expired = lastHiddenAt > 0 && now - lastHiddenAt > SESSION_TIMEOUT_MS;
  if (!sessionId || expired) {
    sessionId = "ws_" + now.toString(36) + "_" + Math.random().toString(36).slice(2, 8);
    entryPage = initialPath || window.location.pathname || "/";
    pushWebTelemetryEvent({
      session_id: sessionId,
      event_type: "session_start",
      event_name: "web_open",
      event_label: "打开 Web 工作台",
      page_path: entryPage,
      page_title: resolvePageTitle(entryPage),
      client_ts: now,
    });
  }
  lastHiddenAt = 0;
}

export function pushWebTelemetryEvent(ev: WebTelemetryEvent) {
  if (typeof window === "undefined") return;
  if (!sessionId && !ev.session_id) {
    ensureSession(ev.page_path);
  }
  const ts = ev.client_ts || Date.now();
  const cleanPath = (ev.page_path || activeRoute || window.location.pathname || "/").split("?")[0];
  const normalized: WebTelemetryEvent = {
    ...ev,
    event_id:
      ev.event_id ||
      `we_${ts.toString(36)}_${(++eventSeq).toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
    session_id: ev.session_id || sessionId,
    page_path: cleanPath,
    page_title: ev.page_title || resolvePageTitle(cleanPath),
    client_ts: ts,
  };
  eventQueue.push(normalized);
  if (eventQueue.length > 100) {
    eventQueue = eventQueue.slice(-100);
  }
  if (eventQueue.length >= 15) {
    flushWebTelemetry(false);
  } else if (!flushTimer) {
    flushTimer = setTimeout(() => {
      flushTimer = null;
      flushWebTelemetry(false);
    }, FLUSH_INTERVAL_MS);
  }
}

export function flushWebTelemetry(useBeacon = false) {
  if (typeof window === "undefined" || eventQueue.length === 0 || isFlushing) return;
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  const batch = eventQueue.splice(0, 60);
  const payload = {
    session_id: batch[0]?.session_id || sessionId,
    client_uuid: getOrCreateClientUuid(),
    entry_page: entryPage || window.location.pathname || "/",
    device_model: typeof navigator !== "undefined" ? navigator.userAgent.slice(0, 80) : "web",
    platform: "web",
    app_version: "2.0.0-web",
    env_version: window.location.hostname === "localhost" ? "develop" : "release",
    events: batch,
  };

  const token = getAuthTokenForTelemetry();
  if (useBeacon && !token && typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
      navigator.sendBeacon("/api/miniapp/telemetry/batch", blob);
      return;
    } catch {}
  }

  isFlushing = true;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  fetch("/api/miniapp/telemetry/batch", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    keepalive: useBeacon,
  })
    .catch(() => {
      // Drop silently on transient offline to avoid blocking Web UX
    })
    .finally(() => {
      isFlushing = false;
    });
}

function finalizeCurrentRoute(reason: string) {
  if (!activeRoute || !activeEnteredAt) return;
  sampleScrollPct();
  const stayMs = Math.max(0, Date.now() - activeEnteredAt);
  pushWebTelemetryEvent({
    event_type: "page_leave",
    event_name: "page_leave",
    event_label: `离开「${resolvePageTitle(activeRoute)}」`,
    page_path: activeRoute,
    page_title: resolvePageTitle(activeRoute),
    stay_ms: stayMs,
    scroll_pct: maxScrollPct || null,
    client_ts: Date.now(),
    props: { reason },
  });
  activeEnteredAt = 0;
}

export function trackWebPageView(pathname: string) {
  if (typeof window === "undefined" || !pathname) return;
  initWebTelemetryOnce();
  const clean = pathname.split("?")[0] || "/";
  ensureSession(clean);

  if (activeRoute && activeRoute !== clean) {
    finalizeCurrentRoute("route_change");
  }
  if (activeRoute !== clean || activeEnteredAt === 0) {
    const prev = activeRoute;
    activeRoute = clean;
    activeEnteredAt = Date.now();
    maxScrollPct = 0;
    pushWebTelemetryEvent({
      event_type: "page_enter",
      event_name: "page_view",
      event_label: `进入「${resolvePageTitle(clean)}」`,
      page_path: clean,
      page_title: resolvePageTitle(clean),
      client_ts: activeEnteredAt,
      props: prev && prev !== clean ? { from_page: prev } : undefined,
    });
    setTimeout(sampleScrollPct, 300);
  }
}

export function initWebTelemetryOnce() {
  if (initialized || typeof window === "undefined") return;
  initialized = true;

  registerWebApiTelemetryReporter((url, method, statusOrErr, durationMs) => {
    if (url.includes("/api/miniapp/telemetry")) return;
    const cleanEndpoint = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const isSlow = typeof statusOrErr === "number" && statusOrErr >= 200 && statusOrErr < 300;
    pushWebTelemetryEvent({
      event_type: "api_issue",
      event_name: isSlow ? "api_slow" : "api_error",
      event_label: isSlow
        ? `Web接口较慢 ${cleanEndpoint} (${Math.round(durationMs)}ms)`
        : `Web接口异常 ${cleanEndpoint} (${statusOrErr})`,
      stay_ms: Math.round(durationMs),
      client_ts: Date.now(),
      props: {
        endpoint: cleanEndpoint,
        method,
        status: statusOrErr,
        duration_ms: Math.round(durationMs),
      },
    });
  });

  window.addEventListener("scroll", sampleScrollPct, { passive: true });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      lastHiddenAt = Date.now();
      finalizeCurrentRoute("tab_hidden");
      flushWebTelemetry(true);
    } else if (document.visibilityState === "visible" && activeRoute) {
      ensureSession(activeRoute);
      activeEnteredAt = Date.now();
    }
  });
  window.addEventListener("pagehide", () => {
    finalizeCurrentRoute("pagehide");
    flushWebTelemetry(true);
  });
}
