/**
 * RGM MiniApp Full-Chain User Behavior Telemetry SDK
 * Silently records per-user journey from launch -> module exposure -> page stay & scroll depth ->
 * button/modal/tab interactions -> API issues -> background/exit, using non-blocking batch uploads.
 */

import { API_BASE_URL, getStoredUser, registerApiTelemetryReporter } from "./api";

declare const wx: any;
declare function getCurrentPages(): any[];
declare function getApp(opts?: any): any;

export type TelemetryEventType =
  | "session_start"
  | "page_enter"
  | "page_leave"
  | "module_view"
  | "button_click"
  | "modal_open"
  | "modal_close"
  | "subview_enter"
  | "funnel_step"
  | "api_issue"
  | "app_background"
  | "session_end";

export interface TelemetryEvent {
  event_id?: string;
  session_id?: string;
  event_type: TelemetryEventType;
  event_name: string;
  event_label?: string;
  page_path?: string;
  page_title?: string;
  stay_ms?: number;
  scroll_pct?: number | null;
  client_ts: number;
  props?: Record<string, any>;
}

const PAGE_TITLES: Record<string, string> = {
  "pages/index/index": "首页",
  "pages/coach/coach": "训练",
  "pages/team/team": "跑团",
  "pages/team/rank": "英雄榜与打卡动态",
  "pages/rank/rank": "英雄榜与打卡动态",
  "pages/team/group-run": "约跑集结与完赛战报",
  "pages/group-run/group-run": "约跑集结与完赛战报",
  "pages/profile/profile": "我的",
  "pages/team/cockpit": "教练工作台",
  "pages/analysis/analysis": "身体数据与跑力分析",
  "pages/activities/activities": "全部跑步记录",
  "pages/onboarding/onboarding": "新手设定引导",
  "pages/manual/manual": "帮助与常见问题",
  "pages/share/share": "邀请海报落地页",
  "pages/goals/goals": "跑量目标设定",
};

const IGNORED_TRANSIENT_ROUTES = new Set<string>([
  "pages/modals/placeholder",
  "pages/team/rank",
  "pages/team/group-run",
]);

const CANONICAL_ROUTE_MAP: Record<string, string> = {
  "pages/team/rank": "pages/rank/rank",
  "pages/team/group-run": "pages/group-run/group-run",
};

const SAFE_QUERY_KEYS = [
  "inviter_uid",
  "club_id",
  "org_id",
  "event_id",
  "activity_id",
  "scene",
  "tab",
];

const STORAGE_QUEUE_KEY = "rgm_telemetry_queue_v2";
const SESSION_TIMEOUT_MS = 5 * 60 * 1000; // 5 min backgrounded starts a new session
const FLUSH_INTERVAL_MS = 8000;
const MAX_QUEUE_LEN = 100;

interface ActivePageState {
  sessionId: string;
  path: string;
  title: string;
  enteredAt: number;
  accumulatedMs: number;
  maxScrollTop: number;
  pageHeight: number;
  reachedBottom: boolean;
  pullRefreshes: number;
  lastViewportSampleAt: number;
}

let sessionId = "";
let sessionActiveMs = 0;
let foregroundEnteredAt = 0;
let lastHiddenAt = 0;
let launchScene: number | undefined = undefined;
let entryPage = "";
let inviterUid = "";

let deviceModel = "";
let devicePlatform = "";
let appVersion = "2.0.0";
let envVersion = "release";
let windowHeight = 750;
let sysInfoLoaded = false;

let activePage: ActivePageState | null = null;
let lastPagePath = "";
let eventQueue: TelemetryEvent[] = [];
let inFlightBatch: TelemetryEvent[] = [];
let persistedQueueLoaded = false;
let eventSeq = 0;
let privacyState: "pending" | "granted" | "denied" = "pending";
let privacyCheckedThisLaunch = false;
let privacyCheckInFlight = false;
let seenModulesInSession = new Set<string>();
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let isFlushing = false;

export function getCurrentSessionId(): string {
  return sessionId;
}

function refreshPrivacyConsent() {
  if (privacyCheckedThisLaunch && privacyState === "granted") return;
  if (privacyCheckInFlight) return;

  if (typeof wx !== "undefined" && wx && typeof wx.getPrivacySetting === "function") {
    try {
      privacyCheckInFlight = true;
      wx.getPrivacySetting({
        success: (res: any) => {
          privacyCheckInFlight = false;
          privacyCheckedThisLaunch = true;
          if (!res?.needAuthorization) {
            privacyState = "granted";
            try {
              uni.setStorageSync("rgm_privacy_consented", "1");
            } catch (_) {}
            ensureSystemInfo();
            loadPersistedQueueOnce();
            if (eventQueue.length > 0) scheduleFlush();
          } else {
            // WeChat requires fresh authorization (e.g. first visit OR updated privacy contract!)
            try {
              uni.removeStorageSync("rgm_privacy_consented");
            } catch (_) {}
            if (privacyState !== "denied") {
              privacyState = "pending";
            }
          }
        },
        fail: () => {
          privacyCheckInFlight = false;
          privacyCheckedThisLaunch = true;
          try {
            if (uni.getStorageSync("rgm_privacy_consented") === "1") {
              privacyState = "granted";
              ensureSystemInfo();
              loadPersistedQueueOnce();
              if (eventQueue.length > 0) scheduleFlush();
            }
          } catch (_) {}
        },
      });
      return;
    } catch (_) {
      privacyCheckInFlight = false;
    }
  }

  privacyCheckedThisLaunch = true;
  privacyState = "granted";
}

export function onTelemetryPrivacyDecision(agreed: boolean) {
  privacyCheckedThisLaunch = true;
  if (agreed) {
    privacyState = "granted";
    try {
      uni.setStorageSync("rgm_privacy_consented", "1");
    } catch (_) {}
    ensureSystemInfo();
    loadPersistedQueueOnce();
    flushTelemetry(false);
  } else {
    privacyState = "denied";
    eventQueue = [];
    inFlightBatch = [];
    try {
      uni.removeStorageSync("rgm_privacy_consented");
      uni.removeStorageSync(STORAGE_QUEUE_KEY);
    } catch (_) {}
  }
}

function ensureSystemInfo() {
  try {
    if (typeof wx !== "undefined" && wx) {
      if (typeof wx.getWindowInfo === "function") {
        const win = wx.getWindowInfo();
        windowHeight = Number(win?.windowHeight) || 750;
      }
      if (typeof wx.getAccountInfoSync === "function") {
        const acc = wx.getAccountInfoSync();
        const mp = acc?.miniProgram;
        if (mp) {
          envVersion = mp.envVersion || "release";
          appVersion = mp.version || "2.0.0";
        }
      }
      // Only read device hardware model after privacy authorization is satisfied
      if (!sysInfoLoaded && privacyState === "granted") {
        sysInfoLoaded = true;
        if (typeof wx.getDeviceInfo === "function") {
          const dev = wx.getDeviceInfo();
          deviceModel = dev?.model || "";
          devicePlatform = dev?.platform || "";
        }
      }
    }
    if (!sysInfoLoaded && privacyState === "granted" && (!deviceModel || !devicePlatform)) {
      sysInfoLoaded = true;
      const sys = uni.getSystemInfoSync();
      deviceModel = deviceModel || sys?.model || "";
      devicePlatform = devicePlatform || sys?.platform || "";
      windowHeight = windowHeight || Number(sys?.windowHeight) || 750;
    }
  } catch (_) {}
}

function sanitizeLaunchQuery(rawQuery: any): Record<string, string> | undefined {
  if (!rawQuery || typeof rawQuery !== "object") return undefined;
  const out: Record<string, string> = {};
  for (const k of SAFE_QUERY_KEYS) {
    const val = rawQuery[k];
    if (val !== undefined && val !== null && String(val).trim() !== "") {
      out[k] = String(val).trim().slice(0, 80);
    }
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

function getOrCreateClientUuid(): string {
  try {
    let cid = uni.getStorageSync("rgm_client_uuid");
    if (!cid) {
      cid = "c_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
      uni.setStorageSync("rgm_client_uuid", cid);
    }
    return String(cid);
  } catch (_) {
    return "c_anon";
  }
}

function getStoredAuthToken(): string {
  try {
    const tk = uni.getStorageSync("rgm_token");
    return tk ? String(tk).trim() : "";
  } catch (_) {
    return "";
  }
}

export function getCurrentPageRoute(): string {
  try {
    if (typeof getCurrentPages === "function") {
      const pages = getCurrentPages();
      if (pages && pages.length > 0) {
        const cur = pages[pages.length - 1];
        const route = cur?.route || cur?.$page?.route || "";
        if (route) return String(route).replace(/^\/+/, "");
      }
    }
  } catch (_) {}
  return activePage?.path || "";
}

function loadPersistedQueueOnce() {
  if (persistedQueueLoaded) return;
  persistedQueueLoaded = true;
  try {
    const raw = uni.getStorageSync(STORAGE_QUEUE_KEY);
    if (Array.isArray(raw) && raw.length > 0) {
      uni.removeStorageSync(STORAGE_QUEUE_KEY);
      const existingIds = new Set(
        inFlightBatch
          .concat(eventQueue)
          .map((e) => e?.event_id)
          .filter(Boolean)
      );
      const deduped = raw.filter((e: any) => !e?.event_id || !existingIds.has(e.event_id));
      eventQueue = deduped.concat(eventQueue).slice(-MAX_QUEUE_LEN);
    }
  } catch (_) {}
}

function persistQueueForCrashSafety() {
  if (privacyState !== "granted") return;
  try {
    const combined = inFlightBatch.concat(eventQueue).slice(-MAX_QUEUE_LEN);
    if (combined.length > 0) {
      uni.setStorageSync(STORAGE_QUEUE_KEY, combined);
    } else {
      uni.removeStorageSync(STORAGE_QUEUE_KEY);
    }
  } catch (_) {}
}

function scheduleFlush() {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flushTelemetry(false);
  }, FLUSH_INTERVAL_MS);
}

function sampleViewportMetrics(force = false) {
  if (!activePage) return;
  const now = Date.now();
  if (!force && now - activePage.lastViewportSampleAt < 2000) return;
  activePage.lastViewportSampleAt = now;
  const targetPage = activePage;
  try {
    uni
      .createSelectorQuery()
      .selectViewport()
      .scrollOffset((res: any) => {
        if (!res || activePage !== targetPage) return;
        const st = Number(res.scrollTop || 0);
        const sh = Number(res.scrollHeight || 0);
        if (st > targetPage.maxScrollTop) {
          targetPage.maxScrollTop = st;
        }
        if (sh > 0) {
          targetPage.pageHeight = sh;
        }
      })
      .exec();
  } catch (_) {}
}

function computeScrollPct(st: ActivePageState): number | null {
  if (st.reachedBottom) return 100;
  if (st.pageHeight > 0) {
    if (st.pageHeight <= windowHeight + 24) {
      return 100;
    }
    return Math.min(100, Math.max(0, Math.round(((st.maxScrollTop + windowHeight) / st.pageHeight) * 100)));
  }
  return null;
}

function ensureSession(options?: any) {
  refreshPrivacyConsent();
  ensureSystemInfo();
  if (privacyState === "granted") {
    loadPersistedQueueOnce();
  }

  const now = Date.now();
  const expired = lastHiddenAt > 0 && now - lastHiddenAt > SESSION_TIMEOUT_MS;

  if (expired && sessionId) {
    // Close out the expired previous session under its own sessionId & lastHiddenAt timestamp
    const prevSid = sessionId;
    const endTs = lastHiddenAt || now;
    if (activePage && activePage.sessionId === prevSid) {
      finalizeActivePage("session_timeout", endTs);
    }
    pushEvent({
      session_id: prevSid,
      event_type: "session_end",
      event_name: "session_timeout_end",
      event_label: "后台超时结束会话",
      page_path: lastPagePath || undefined,
      stay_ms: sessionActiveMs,
      client_ts: endTs,
    });
  }

  if (!sessionId || expired) {
    sessionId = "s_" + now.toString(36) + "_" + Math.random().toString(36).substring(2, 8);
    sessionActiveMs = 0;
    lastPagePath = "";
    seenModulesInSession = new Set<string>();

    if (options?.scene !== undefined && options?.scene !== null) {
      const parsed = Number(options.scene);
      if (!Number.isNaN(parsed)) launchScene = parsed;
    }
    if (options?.path) {
      const rawEntry = String(options.path).replace(/^\/+/, "");
      entryPage = CANONICAL_ROUTE_MAP[rawEntry] || rawEntry;
    }
    if (options?.query?.inviter_uid) {
      inviterUid = String(options.query.inviter_uid).slice(0, 80);
    }

    pushEvent({
      session_id: sessionId,
      event_type: "session_start",
      event_name: "app_open",
      event_label: "打开小程序",
      page_path: entryPage || getCurrentPageRoute() || "pages/index/index",
      client_ts: now,
      props: {
        scene: launchScene,
        query: sanitizeLaunchQuery(options?.query),
      },
    });
  } else if (options?.query?.scene && String(options.query.scene).includes("wlogin_")) {
    pushEvent({
      session_id: sessionId,
      event_type: "funnel_step",
      event_name: "app_reopen_scan",
      event_label: "热启动扫码登录",
      page_path: options?.path ? String(options.path).replace(/^\/+/, "") : getCurrentPageRoute() || "pages/share/share",
      client_ts: now,
      props: {
        scene: options?.scene !== undefined ? Number(options.scene) : launchScene,
        query: sanitizeLaunchQuery(options?.query),
      },
    });
  }

  foregroundEnteredAt = now;
  lastHiddenAt = 0;
}

function pushEvent(ev: TelemetryEvent) {
  if (privacyState === "denied") return;
  if (!sessionId && !ev.session_id) {
    ensureSession();
  }
  const route = ev.page_path || getCurrentPageRoute();
  const rawCleanPath = route ? route.replace(/^\/+/, "").split("?")[0] : "";
  const cleanPath = rawCleanPath ? CANONICAL_ROUTE_MAP[rawCleanPath] || rawCleanPath : "";
  if (cleanPath && IGNORED_TRANSIENT_ROUTES.has(cleanPath)) return;
  const ts = ev.client_ts || Date.now();
  const eid =
    ev.event_id ||
    `e_${ts.toString(36)}_${(++eventSeq).toString(36)}_${Math.random().toString(36).slice(2, 6)}`;

  const normalized: TelemetryEvent = {
    ...ev,
    event_id: eid,
    session_id: ev.session_id || sessionId,
    page_path: cleanPath || undefined,
    page_title: ev.page_title || (cleanPath ? PAGE_TITLES[cleanPath] || cleanPath : undefined),
    client_ts: ts,
  };

  eventQueue.push(normalized);
  if (eventQueue.length > MAX_QUEUE_LEN) {
    eventQueue = eventQueue.slice(-MAX_QUEUE_LEN);
  }

  if (privacyState !== "granted") return;

  if (eventQueue.length >= 15) {
    flushTelemetry(false);
  } else {
    scheduleFlush();
  }
}

export function flushTelemetry(immediate = false) {
  if (flushTimer && immediate) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  if (privacyState !== "granted") return;
  if (eventQueue.length === 0) return;

  // Always persist first when called immediately (e.g. App.onHide) in case OS suspends in-flight request
  if (immediate) {
    persistQueueForCrashSafety();
  }

  if (isFlushing) return;
  ensureSystemInfo();
  const primarySid = eventQueue[0]?.session_id || sessionId;
  if (!primarySid) return;

  isFlushing = true;
  const batch = eventQueue.splice(0, 60);
  inFlightBatch = batch;
  const token = getStoredAuthToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const payload = {
    session_id: sessionId || primarySid,
    client_uuid: getOrCreateClientUuid(),
    scene: launchScene,
    entry_page: entryPage || undefined,
    inviter_uid: inviterUid || undefined,
    device_model: deviceModel || undefined,
    platform: devicePlatform || undefined,
    app_version: appVersion || undefined,
    env_version: envVersion || undefined,
    events: batch,
  };

  try {
    uni.request({
      url: `${API_BASE_URL}/api/miniapp/telemetry/batch`,
      method: "POST",
      data: payload,
      timeout: 5000,
      header: headers,
      success: (res) => {
        isFlushing = false;
        inFlightBatch = [];
        if (res.statusCode >= 200 && res.statusCode < 300) {
          persistQueueForCrashSafety();
          if (eventQueue.length > 0) {
            scheduleFlush();
          }
        } else {
          eventQueue = batch.concat(eventQueue).slice(-MAX_QUEUE_LEN);
          persistQueueForCrashSafety();
        }
      },
      fail: () => {
        isFlushing = false;
        inFlightBatch = [];
        eventQueue = batch.concat(eventQueue).slice(-MAX_QUEUE_LEN);
        persistQueueForCrashSafety();
      },
    });
  } catch (_) {
    isFlushing = false;
    inFlightBatch = [];
    eventQueue = batch.concat(eventQueue).slice(-MAX_QUEUE_LEN);
    persistQueueForCrashSafety();
  }
}

function finalizeActivePage(
  reason: "route_change" | "unload" | "session_timeout",
  overrideEndTs?: number
) {
  if (!activePage) return;
  const endTs = overrideEndTs || Date.now();
  const delta = activePage.enteredAt > 0 ? Math.max(0, endTs - activePage.enteredAt) : 0;
  const totalStayMs = activePage.accumulatedMs + delta;
  const scrollPct = computeScrollPct(activePage);

  if (totalStayMs >= 150) {
    pushEvent({
      session_id: activePage.sessionId || sessionId,
      event_type: "page_leave",
      event_name: "page_stay",
      event_label: `离开「${activePage.title}」`,
      page_path: activePage.path,
      page_title: activePage.title,
      stay_ms: totalStayMs,
      scroll_pct: scrollPct,
      client_ts: endTs,
      props: {
        max_scroll_px: Math.round(activePage.maxScrollTop),
        reached_bottom: activePage.reachedBottom,
        pull_refreshes: activePage.pullRefreshes || undefined,
        leave_reason: reason,
      },
    });
  }

  lastPagePath = activePage.path;
  activePage = null;
}

// ── App Lifecycle Hooks (wired in App.vue) ───────────────────────────────────

export function onTelemetryAppLaunch(options?: any) {
  ensureSystemInfo();
  installGlobalTrackerBridge();
  ensureSession(options);
}

export function onTelemetryAppShow(options?: any) {
  installGlobalTrackerBridge();
  ensureSession(options);
}

export function onTelemetryAppHide() {
  const now = Date.now();
  if (foregroundEnteredAt > 0) {
    sessionActiveMs += Math.max(0, now - foregroundEnteredAt);
    foregroundEnteredAt = 0;
  }
  lastHiddenAt = now;

  // Pause active page timer WITHOUT destroying activePage so system pickers
  // (chooseAvatar / chooseImage / chooseMessageFile / previewImage) don't fake exits or duplicate PVs
  if (activePage && activePage.enteredAt > 0) {
    activePage.accumulatedMs += Math.max(0, now - activePage.enteredAt);
    activePage.enteredAt = 0;
  }

  pushEvent({
    session_id: sessionId,
    event_type: "app_background",
    event_name: "app_background",
    event_label: "切入后台/系统选择器",
    page_path: activePage?.path || lastPagePath || getCurrentPageRoute(),
    stay_ms: sessionActiveMs,
    scroll_pct: activePage ? computeScrollPct(activePage) : null,
    client_ts: now,
  });

  persistQueueForCrashSafety();
  flushTelemetry(true);
}

// ── Public Action & Module Exposure Tracking Helpers ─────────────────────────

export function trackClick(eventName: string, eventLabel: string, props?: Record<string, any>) {
  try {
    sampleViewportMetrics(false);
    pushEvent({
      event_type: "button_click",
      event_name: eventName,
      event_label: eventLabel,
      client_ts: Date.now(),
      props,
    });
  } catch (_) {}
}

export function trackModal(
  eventName: string,
  eventLabel: string,
  action: "open" | "close" | "submit" = "open",
  props?: Record<string, any>
) {
  try {
    sampleViewportMetrics(false);
    const evType: TelemetryEventType =
      action === "open" ? "modal_open" : action === "close" ? "modal_close" : "funnel_step";
    pushEvent({
      event_type: evType,
      event_name: `${eventName}_${action}`,
      event_label: eventLabel,
      client_ts: Date.now(),
      props: { modal: eventName, action, ...(props || {}) },
    });
  } catch (_) {}
}

export function trackSubView(subViewKey: string, subViewLabel: string, props?: Record<string, any>) {
  try {
    sampleViewportMetrics(false);
    pushEvent({
      event_type: "subview_enter",
      event_name: `subview_${subViewKey}`,
      event_label: subViewLabel,
      client_ts: Date.now(),
      props,
    });
  } catch (_) {}
}

export function trackFunnelStep(stepName: string, stepLabel: string, props?: Record<string, any>) {
  try {
    pushEvent({
      event_type: "funnel_step",
      event_name: stepName,
      event_label: stepLabel,
      client_ts: Date.now(),
      props,
    });
    // If user just logged in or completed a key step, flush promptly with latest token
    if (
      stepName.includes("login") ||
      stepName.includes("bind_") ||
      stepName.includes("club_") ||
      stepName.includes("member_") ||
      stepName.includes("onboarding_") ||
      stepName.includes("plan_")
    ) {
      setTimeout(() => flushTelemetry(false), 300);
    }
  } catch (_) {}
}

export function trackModuleView(moduleKey: string, moduleLabel: string, props?: Record<string, any>) {
  try {
    if (!sessionId) ensureSession();
    const dedupKey = `${sessionId}:${moduleKey}`;
    if (seenModulesInSession.has(dedupKey)) return;
    seenModulesInSession.add(dedupKey);
    pushEvent({
      event_type: "module_view",
      event_name: moduleKey,
      event_label: moduleLabel,
      client_ts: Date.now(),
      props,
    });
  } catch (_) {}
}

export interface ModuleExposureTarget {
  selector: string;
  key: string;
  label: string;
}

/**
 * Attaches lightweight IntersectionObserver (threshold 0.35) to measure card-level exposure
 * without per-frame onPageScroll bridge overhead. Returns a cleanup function.
 */
export function observeModuleExposures(
  vmInstance: any,
  targets: ModuleExposureTarget[]
): () => void {
  const observers: any[] = [];
  try {
    for (const item of targets) {
      const obs = uni.createIntersectionObserver(vmInstance, { thresholds: [0.35] });
      obs.relativeToViewport({ bottom: 0 }).observe(item.selector, (res: any) => {
        if (res && Number(res.intersectionRatio || 0) >= 0.3) {
          sampleViewportMetrics(false);
          trackModuleView(item.key, item.label);
        }
      });
      observers.push(obs);
    }
  } catch (_) {}

  return () => {
    for (const obs of observers) {
      try {
        obs.disconnect();
      } catch (_) {}
    }
  };
}

export function trackApiIssue(
  url: string,
  method: string,
  statusOrErr: number | string,
  durationMs: number
) {
  try {
    if (url.includes("/api/miniapp/telemetry")) return;
    const cleanEndpoint = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    const isSlow = typeof statusOrErr === "number" && statusOrErr >= 200 && statusOrErr < 300;
    pushEvent({
      event_type: "api_issue",
      event_name: isSlow ? "api_slow" : "api_error",
      event_label: isSlow
        ? `接口较慢 ${cleanEndpoint} (${Math.round(durationMs)}ms)`
        : `接口异常 ${cleanEndpoint} (${statusOrErr})`,
      stay_ms: Math.round(durationMs),
      client_ts: Date.now(),
      props: {
        endpoint: cleanEndpoint,
        method,
        status: statusOrErr,
        duration_ms: Math.round(durationMs),
      },
    });
  } catch (_) {}
}

function installGlobalTrackerBridge() {
  try {
    registerApiTelemetryReporter(trackApiIssue);
    const fn = (
      eventType: TelemetryEventType,
      eventName: string,
      eventLabel: string,
      props?: Record<string, any>
    ) => {
      sampleViewportMetrics(false);
      pushEvent({
        event_type: eventType || "button_click",
        event_name: eventName,
        event_label: eventLabel,
        client_ts: Date.now(),
        props,
      });
    };
    if (typeof wx !== "undefined" && wx) {
      wx.$rgmTrack = fn;
    }
    if (typeof getApp === "function") {
      const app = getApp({ allowDefault: true });
      if (app) app.$rgmTrack = fn;
    }
  } catch (_) {}
}

// ── Global Vue Page Mixin (installed once in main.ts) ────────────────────────

function isPageInstance(vm: any): boolean {
  if (!vm) return false;
  const mpType = vm.$mpType || vm.$?.type?.mpType || vm.$options?.mpType;
  if (mpType) return mpType === "page";
  try {
    if (typeof getCurrentPages === "function") {
      const pages = getCurrentPages();
      const top = pages && pages.length ? pages[pages.length - 1] : null;
      if (top && ((vm.$scope && top === vm.$scope) || top.$vm === vm)) {
        return true;
      }
    }
  } catch (_) {}
  return false;
}

export const telemetryPageMixin = {
  onShow(this: any) {
    if (!isPageInstance(this)) return;
    try {
      const path = getCurrentPageRoute();
      if (!path || IGNORED_TRANSIENT_ROUTES.has(path)) return;
      if (!sessionId) ensureSession();

      if (activePage && activePage.path !== path) {
        finalizeActivePage("route_change");
      }

      if (!activePage || activePage.path !== path || activePage.sessionId !== sessionId) {
        const title = PAGE_TITLES[path] || path;
        activePage = {
          sessionId,
          path,
          title,
          enteredAt: Date.now(),
          accumulatedMs: 0,
          maxScrollTop: 0,
          pageHeight: 0,
          reachedBottom: false,
          pullRefreshes: 0,
          lastViewportSampleAt: 0,
        };
        if (!entryPage) entryPage = path;
        pushEvent({
          event_type: "page_enter",
          event_name: "page_view",
          event_label: `进入「${title}」`,
          page_path: path,
          page_title: title,
          client_ts: activePage.enteredAt,
          props: lastPagePath && lastPagePath !== path ? { from_page: lastPagePath } : undefined,
        });
        setTimeout(() => sampleViewportMetrics(true), 350);
      } else if (activePage.enteredAt === 0) {
        // Resumed from brief background / picker within same session — resume timer without inflating PV
        activePage.enteredAt = Date.now();
        setTimeout(() => sampleViewportMetrics(true), 350);
      }
    } catch (_) {}
  },

  onHide(this: any) {
    if (!isPageInstance(this)) return;
    try {
      const path = getCurrentPageRoute();
      // Only finalize when route actually changed (navigateTo / switchTab);
      // App.onHide handles app backgrounding / native pickers without destroying activePage
      if (activePage && path && path !== activePage.path) {
        finalizeActivePage("route_change");
      }
    } catch (_) {}
  },

  onUnload(this: any) {
    if (!isPageInstance(this)) return;
    try {
      finalizeActivePage("unload");
    } catch (_) {}
  },

  onReachBottom(this: any) {
    if (activePage) {
      activePage.reachedBottom = true;
    }
  },

  onPullDownRefresh(this: any) {
    if (activePage) {
      activePage.pullRefreshes += 1;
      trackClick("pull_down_refresh", `下拉刷新「${activePage.title}」`);
    }
  },
};
