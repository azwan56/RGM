import { createClient } from "@supabase/supabase-js";
import axios from "axios";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "http://localhost:8000";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.fake_anon_key";

const baseSupabase = createClient(supabaseUrl, supabaseAnonKey);

const isBrowser = typeof window !== "undefined";
const AUTH_KEY = "rgm_auth_session";

// Listener callbacks for auth state changes
const authListeners = new Set<(event: string, session: any) => void>();

function notifyListeners(event: string, session: any) {
  authListeners.forEach((cb) => {
    try {
      cb(event, session);
    } catch (e) {
      console.error("[auth] listener error:", e);
    }
  });
}

// Robust auth provider
const customAuth = {
  ...baseSupabase.auth,

  async signUp({ email, password, options }: { email: string; password: string; options?: any }) {
    try {
      const res = await axios.post("/api/auth/email/signup", {
        email,
        password,
        display_name: options?.data?.display_name || email.split("@")[0],
      });
      const session = {
        access_token: res.data.token,
        token_type: "bearer",
        user: res.data.user,
      };
      if (isBrowser) {
        localStorage.setItem(AUTH_KEY, JSON.stringify(session));
      }
      notifyListeners("SIGNED_IN", session);
      return { data: { user: res.data.user, session }, error: null };
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "注册失败";
      return { data: { user: null, session: null }, error: new Error(msg) };
    }
  },

  async signInWithPassword({ email, password }: { email: string; password: string }) {
    try {
      const res = await axios.post("/api/auth/email/login", {
        email,
        password,
      });
      const session = {
        access_token: res.data.token,
        token_type: "bearer",
        user: res.data.user,
      };
      if (isBrowser) {
        localStorage.setItem(AUTH_KEY, JSON.stringify(session));
      }
      notifyListeners("SIGNED_IN", session);
      return { data: { user: res.data.user, session }, error: null };
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "登录失败";
      return { data: { user: null, session: null }, error: new Error(msg) };
    }
  },

  async getSession() {
    if (isBrowser) {
      const raw = localStorage.getItem(AUTH_KEY);
      if (raw) {
        try {
          const session = JSON.parse(raw);
          return { data: { session }, error: null };
        } catch (e) {
          localStorage.removeItem(AUTH_KEY);
        }
      }
    }
    return { data: { session: null }, error: null };
  },

  async getUser() {
    const { data } = await this.getSession();
    return { data: { user: data?.session?.user || null }, error: null };
  },

  async signOut() {
    if (isBrowser) {
      localStorage.removeItem(AUTH_KEY);
    }
    notifyListeners("SIGNED_OUT", null);
    return { error: null };
  },

  onAuthStateChange(callback: (event: string, session: any) => void) {
    authListeners.add(callback);
    // Trigger initial session check
    this.getSession().then(({ data }) => {
      callback(data?.session ? "SIGNED_IN" : "SIGNED_OUT", data?.session || null);
    });
    return {
      data: {
        subscription: {
          unsubscribe: () => {
            authListeners.delete(callback);
          },
        },
      },
    };
  },
};

export const supabase = {
  ...baseSupabase,
  auth: customAuth,
};
