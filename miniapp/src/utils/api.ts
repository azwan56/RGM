/**
 * RGM Mini Program API Client & Auth Manager
 */

// Configure Backend Base URL (Aliyun ECS Production Domain)
export const API_BASE_URL = "https://rgm.vanpower.net";

export interface UserProfile {
  id: string;
  display_name: string;
  avatar_url?: string;
  phone?: string;
  garmin_connected: boolean;
  garmin_email?: string;
  garmin_domain?: string;
  max_heart_rate?: number;
  resting_heart_rate?: number;
  marathon_pb?: number;
}

export function getToken(): string {
  return uni.getStorageSync("rgm_token") || "";
}

export function getStoredUser(): UserProfile | null {
  const data = uni.getStorageSync("rgm_user");
  if (!data) return null;
  try {
    const parsed = JSON.parse(data);
    if (parsed && parsed.id) return parsed;
  } catch (e) {
    console.error("Failed to parse stored user", e);
  }
  return null;
}

export function setSession(token: string, user: UserProfile) {
  if (token) uni.setStorageSync("rgm_token", token);
  if (user) uni.setStorageSync("rgm_user", JSON.stringify(user));
}

export function clearSession() {
  uni.removeStorageSync("rgm_token");
  uni.removeStorageSync("rgm_user");
}

/**
 * Universal Request Wrapper with Bearer Token Injection
 */
export async function request<T = any>(
  url: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: any
): Promise<T> {
  const token = getToken();
  const fullUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;

  return new Promise((resolve, reject) => {
    uni.request({
      url: fullUrl,
      method,
      data,
      timeout: 90000,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T);
        } else if (res.statusCode === 401) {
          clearSession();
          uni.showToast({ title: "登录已过期，请重新登录", icon: "none" });
          reject(new Error("Unauthorized"));
        } else {
          const errMsg = (res.data as any)?.detail || (res.data as any)?.message || (res.data as any)?.error || `请求失败 (${res.statusCode})`;
          reject(new Error(errMsg));
        }
      },
      fail: (err) => {
        console.error(`[API Network Error] ${fullUrl}`, err);
        let errDesc = "网络异常，请检查网络连接";
        if (err?.errMsg) {
          if (err.errMsg.includes("url not in domain list")) {
            errDesc = "域名未授权：请在微信开发者工具右上角【详情】->【本地设置】勾选【不校验合法域名】";
          } else if (err.errMsg.includes("timeout")) {
            errDesc = "连接超时：佳明官方服务器验证较慢，请稍后重试";
          } else {
            errDesc = `网络连接异常 (${err.errMsg})`;
          }
        }
        reject(new Error(errDesc));
      },
    });
  });
}

/**
 * Executes WeChat wx.login and syncs with backend
 */
export async function wechatLogin(): Promise<UserProfile | null> {
  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success: async (loginRes) => {
        if (loginRes.code) {
          try {
            console.log("[wechatLogin] wx.login success, code:", loginRes.code);
            const data = await request("/api/auth/wechat/miniapp-login", "POST", {
              code: loginRes.code,
            });

            const uid = data.uid || data.profile?.id || `user_${loginRes.code.substring(0, 8)}`;
            const profile: UserProfile = {
              id: uid,
              display_name: data.display_name || data.profile?.display_name || "微信跑者",
              avatar_url: data.avatar_url || data.profile?.avatar_url || "",
              garmin_connected: Boolean(data.garmin_connected || data.profile?.garmin_connected),
              garmin_email: data.profile?.garmin_email || "",
              garmin_domain: data.profile?.garmin_domain || "garmin.cn",
            };

            setSession(data.token || "dev_token", profile);
            console.log("[wechatLogin] User session saved:", profile);
            resolve(profile);
          } catch (e: any) {
            console.error("[wechatLogin] backend login error:", e);
            // Fallback for offline/development test
            const fallbackUser: UserProfile = {
              id: `dev_user_${loginRes.code.substring(0, 8)}`,
              display_name: "微信跑者",
              garmin_connected: false,
            };
            setSession("dev_token", fallbackUser);
            resolve(fallbackUser);
          }
        } else {
          uni.showToast({ title: "微信登录授权失败", icon: "none" });
          reject(new Error("No code returned from wx.login"));
        }
      },
      fail: (err) => {
        console.error("[wechatLogin] wx.login fail:", err);
        // Fallback user if wx.login fails
        const fallbackUser: UserProfile = {
          id: "dev_runner_demo",
          display_name: "微信跑者",
          garmin_connected: false,
        };
        setSession("dev_token", fallbackUser);
        resolve(fallbackUser);
      },
    });
  });
}

/**
 * Executes email registration and syncs with backend
 */
export async function emailSignUp(email: string, password: string, displayName?: string): Promise<UserProfile> {
  const data = await request("/api/auth/email/signup", "POST", {
    email,
    password,
    display_name: displayName,
  });

  const profile: UserProfile = {
    id: data.user.id,
    display_name: data.user.display_name || email.split("@")[0],
    garmin_connected: Boolean(data.user.garmin_connected),
    garmin_email: data.user.email,
  };
  setSession(data.token, profile);
  return profile;
}

/**
 * Executes email login and syncs with backend
 */
export async function emailLogin(email: string, password: string): Promise<UserProfile> {
  const data = await request("/api/auth/email/login", "POST", {
    email,
    password,
  });

  const profile: UserProfile = {
    id: data.user.id,
    display_name: data.user.display_name || email.split("@")[0],
    garmin_connected: Boolean(data.user.garmin_connected),
    garmin_email: data.user.email,
  };
  setSession(data.token, profile);
  return profile;
}

/**
 * Auto login check on app startup
 */
export async function checkAndAutoLogin() {
  const user = getStoredUser();
  if (!user || !user.id) {
    try {
      await wechatLogin();
    } catch (e) {
      console.warn("Auto login deferred:", e);
    }
  }
}

