import axios from "axios";
import { supabase } from "./supabase";

const apiClient = axios.create({
  baseURL: typeof window !== "undefined" ? "" : (process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000"),
});

// Request interceptor to automatically inject JWT
apiClient.interceptors.request.use(
  async (config) => {
    try {
      if (typeof window !== "undefined") {
        const { data } = await supabase.auth.getSession();
        let token = data?.session?.access_token || (data?.session as any)?.token;
        if (!token) {
          try {
            const raw = localStorage.getItem("rgm_auth_session");
            if (raw) {
              const sess = JSON.parse(raw);
              token = sess?.access_token || sess?.token;
            }
          } catch {}
        }
        if (!token) {
          token = localStorage.getItem("rgm_token") || localStorage.getItem("rgm_admin_token");
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
  (response) => response,
  (error) => {
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
    return Promise.reject(error);
  }
);

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
