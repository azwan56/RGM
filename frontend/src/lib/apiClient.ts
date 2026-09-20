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

export default apiClient;
