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

  async signInWithWatch({
    brand,
    account,
    password,
    domain,
    mfaCode,
  }: {
    brand: "coros" | "garmin";
    account: string;
    password: string;
    domain?: string;
    mfaCode?: string;
  }) {
    try {
      const payload: Record<string, any> = {
        brand,
        account: account.trim(),
        password: password.trim(),
        domain: domain || (brand === "coros" ? "teamcnapi.coros.com" : "garmin.cn"),
      };
      if (mfaCode && mfaCode.trim()) {
        payload.mfa_code = mfaCode.trim();
      }
      const res = await axios.post("/api/auth/device-login", payload);
      if (res.data?.needs_2fa || res.data?.needs_mfa) {
        return {
          data: {
            user: null,
            session: null,
            needsMfa: true,
            message: res.data.message || "已向您的手机或邮箱发送 6 位安全验证码，请输入验证码完成登录",
          },
          error: null,
        };
      }
      const userObj = res.data.user || {
        id: res.data.uid,
        email: res.data.garmin_email || res.data.coros_account || account.trim(),
        display_name: res.data.display_name || account.trim(),
        avatar_url: res.data.avatar_url || "",
        garmin_connected: Boolean(res.data.garmin_connected || res.data.coros_connected),
        coros_connected: Boolean(res.data.coros_connected),
        is_coach_or_owner: Boolean(res.data.is_coach_or_owner),
      };
      const session = {
        access_token: res.data.token,
        token_type: "bearer",
        user: userObj,
      };
      if (isBrowser) {
        localStorage.setItem(AUTH_KEY, JSON.stringify(session));
      }
      notifyListeners("SIGNED_IN", session);
      return { data: { user: userObj, session, needsMfa: false }, error: null };
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "手表账号验证失败，请核对账号密码与所属区域";
      return { data: { user: null, session: null, needsMfa: false }, error: new Error(msg) };
    }
  },

  async completeTokenSession(token: string, user: any) {
    const session = {
      access_token: token,
      token_type: "bearer",
      user,
    };
    if (isBrowser) {
      localStorage.setItem(AUTH_KEY, JSON.stringify(session));
    }
    notifyListeners("SIGNED_IN", session);
    return { data: { user, session }, error: null };
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
