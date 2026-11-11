import axios, { type AxiosRequestConfig, type AxiosResponse } from "axios";
import { supabase } from "./supabase";

type ApiTelemetryReporter = (
  url: string,
  method: string,
  statusOrErr: number | string,
  durationMs: number
) => void;

let _webApiTelemetryReporter: ApiTelemetryReporter | null = null;

export function registerWebApiTelemetryReporter(fn: ApiTelemetryReporter) {
  _webApiTelemetryReporter = fn;
}

function getCachedTokenSync(): string {
  if (typeof window === "undefined") return "";
  try {
    const raw = localStorage.getItem("rgm_auth_session");
    if (raw) {
      const sess = JSON.parse(raw);
      const t = sess?.access_token || sess?.token;
      if (t) return String(t);
    }
  } catch {}
  try {
    return localStorage.getItem("rgm_token") || localStorage.getItem("rgm_admin_token") || "";
  } catch {
    return "";
  }
}

const apiClient = axios.create({
  baseURL: typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"),
});

// Request interceptor to automatically inject JWT and stamp start timestamp
apiClient.interceptors.request.use(
  async (config) => {
    (config as any).__rgmStartedAt = Date.now();
    try {
      if (typeof window !== "undefined") {
        const { data } = await supabase.auth.getSession();
        let token = data?.session?.access_token || (data?.session as any)?.token;
        if (!token) {
          token = getCachedTokenSync();
        }
        if (token) {
          if (config.headers && typeof (config.headers as any).set === "function") {
            (config.headers as any).set("Authorization", `Bearer ${token}`);
          } else {
            config.headers = config.headers || {};
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
      }
    } catch (err) {
      console.error("[apiClient] Failed to attach token:", err);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => {
    const startedAt = Number((response.config as any)?.__rgmStartedAt || 0);
    const elapsedMs = startedAt > 0 ? Date.now() - startedAt : 0;
    if (elapsedMs >= 3500 && _webApiTelemetryReporter && response.config?.url) {
      try {
        _webApiTelemetryReporter(
          response.config.url,
          String(response.config.method || "GET").toUpperCase(),
          response.status,
          elapsedMs
        );
      } catch {}
    }
    return response;
  },
  (error) => {
    const cfg = error?.config || {};
    const startedAt = Number(cfg.__rgmStartedAt || 0);
    const elapsedMs = startedAt > 0 ? Date.now() - startedAt : 0;
    if (error.response?.data?.detail) {
      const raw = error.response.data.detail;
      if (Array.isArray(raw)) {
        error.response.data.detail = raw
          .map((item: any) => {
            if (typeof item === "string") return item;
            if (item?.msg) {
              const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
              return field ? `${field}: ${item.msg}` : item.msg;
            }
            return JSON.stringify(item);
          })
          .join("; ");
      } else if (typeof raw === "object" && raw !== null) {
        error.response.data.detail = raw.message || raw.msg || JSON.stringify(raw);
      }
    }
    if (_webApiTelemetryReporter && cfg?.url && error?.code !== "ERR_CANCELED") {
      try {
        const statusOrErr = error?.response?.status
          ? `${error.response.status}: ${String(error.response?.data?.detail || error.message || "").slice(0, 60)}`
          : String(error?.message || "network_error").slice(0, 60);
        _webApiTelemetryReporter(
          cfg.url,
          String(cfg.method || "GET").toUpperCase(),
          statusOrErr,
          elapsedMs
        );
      } catch {}
    }
    return Promise.reject(error);
  }
);

// Transparent In-Flight GET Request Deduplication:
// Coalesces simultaneous identical GET requests across mounted React components into a single HTTP flight.
const _inflightGets = new Map<string, Promise<any>>();
const _rawGet = apiClient.get.bind(apiClient);

const _dedupGet = function deduplicatedGet<T = any, R = AxiosResponse<T>, D = any>(
  url: string,
  config?: AxiosRequestConfig<D>
): Promise<R> {
  if (typeof window === "undefined" || config?.signal || config?.cancelToken) {
    return _rawGet(url, config) as unknown as Promise<R>;
  }
  let serializedParams = "";
  if (config?.params !== undefined) {
    try {
      serializedParams = JSON.stringify(config.params);
    } catch {}
  }
  const tokenTail = getCachedTokenSync().slice(-16);
  const dedupKey = `${tokenTail}|${url}|${serializedParams}`;
  const existing = _inflightGets.get(dedupKey);
  if (existing) {
    return existing as Promise<R>;
  }
  const reqPromise = _rawGet(url, config) as unknown as Promise<R>;
  _inflightGets.set(dedupKey, reqPromise);
  reqPromise.finally(() => {
    if (_inflightGets.get(dedupKey) === reqPromise) {
      _inflightGets.delete(dedupKey);
    }
  });
  return reqPromise;
};

(apiClient as any).get = _dedupGet;

export function formatBeijingTime(isoStr?: string | null, withYear = false): string {
  if (!isoStr) return "";
  const raw = String(isoStr).trim();
  if (!raw) return "";
  const hasTz = /[Zz]$|[+-]\d{2}:?\d{2}$/.test(raw);
  if (hasTz) {
    const normalized = raw.replace(" ", "T").replace(/\.(\d{3})\d+/, ".$1");
    const d = new Date(normalized);
    if (!isNaN(d.getTime())) {
      const bj = new Date(d.getTime() + 8 * 3600 * 1000);
      const yyyy = bj.getUTCFullYear();
      const mm = String(bj.getUTCMonth() + 1).padStart(2, "0");
      const dd = String(bj.getUTCDate()).padStart(2, "0");
      const hh = String(bj.getUTCHours()).padStart(2, "0");
      const mi = String(bj.getUTCMinutes()).padStart(2, "0");
      return withYear ? `${yyyy}-${mm}-${dd} ${hh}:${mi}` : `${mm}-${dd} ${hh}:${mi}`;
    }
  }
  const clean = raw.replace("T", " ");
  if (clean.length >= 16) {
    return withYear ? clean.slice(0, 16) : clean.slice(5, 16);
  }
  return clean;
}

export default apiClient;
