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
        const token = data?.session?.access_token;
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
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
