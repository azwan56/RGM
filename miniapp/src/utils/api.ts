/**
 * RGM Mini Program API Client & Auth Manager
 * Pure WeChat One-Click Authentication & User Session Management
 */

// Configure Backend Base URL (Aliyun ECS Production Domain)
export const API_BASE_URL = "https://rgm.vanpower.net";

declare const wx: any;

export interface UserProfile {
  id: string;
  display_name: string;
  avatar_url?: string;
  phone?: string;
  garmin_connected: boolean;
  garmin_email?: string;
  garmin_domain?: string;
  coros_connected?: boolean;
  coros_account?: string;
  coros_domain?: string;
  max_heart_rate?: number;
  resting_heart_rate?: number;
  vo2max?: number;
  marathon_pb?: number;
}

export function getToken(): string {
  return uni.getStorageSync("rgm_token") || "";
}

/**
 * Returns current logged-in user profile from local storage, or null if not logged in.
 * STRICTLY NO HARDCODED DEFAULT USER.
 */
export function getStoredUser(): UserProfile | null {
  const data = uni.getStorageSync("rgm_user");
  if (data) {
    if (typeof data === "object" && data.id) {
      return data as UserProfile;
    }
    if (typeof data === "string") {
      try {
        const parsed = JSON.parse(data);
        if (parsed && parsed.id) return parsed as UserProfile;
      } catch (e) {
        // invalid json
      }
    }
  }
  return null;
}

export function setSession(token: string, user: UserProfile) {
  if (token) uni.setStorageSync("rgm_token", token);
  if (user) uni.setStorageSync("rgm_user", user);
}

export function clearSession() {
  uni.removeStorageSync("rgm_token");
  uni.removeStorageSync("rgm_user");
  // NOTE: Never remove rgm_client_uuid: it is the permanent physical device identifier
}

/**
 * Get the currently active running club ID from local storage.
 */
export function getActiveClubId(): string {
  return uni.getStorageSync("rgm_active_club_id") || "";
}

/**
 * Set the currently active running club ID to local storage.
 */
export function setActiveClubId(clubId: string) {
  if (clubId) {
    uni.setStorageSync("rgm_active_club_id", clubId);
  } else {
    uni.removeStorageSync("rgm_active_club_id");
  }
}

/**
 * Given a list of clubs, resolves which one is active based on storage or defaults to the first.
 */
export function resolveActiveClub(clubs: any[]): any | null {
  if (!clubs || clubs.length === 0) {
    setActiveClubId("");
    return null;
  }
  const storedId = getActiveClubId();
  if (storedId) {
    const matched = clubs.find((c) => c.id === storedId);
    if (matched) return matched;
  }
  const primary = clubs[0];
  setActiveClubId(primary.id);
  return primary;
}

/**
 * Universal Request Wrapper with Bearer Token Injection
 */
export async function request<T = any>(
  url: string,
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" = "GET",
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
          uni.showToast({ title: "登录已失效，正在重新登录", icon: "none" });
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
 * Executes WeChat wx.login and syncs unique user with backend.
 * Features dual wx/uni compatibility and seamless local device fallback so UI never hangs.
 */
export async function wechatLogin(forceNew = false): Promise<UserProfile | null> {
  return new Promise((resolve) => {
    let resolved = false;
    let clientUuid = uni.getStorageSync("rgm_client_uuid");
    if (!clientUuid || forceNew) {
      clientUuid = "c_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
      uni.setStorageSync("rgm_client_uuid", clientUuid);
    }

    const fallbackUser = (): UserProfile => {
      const uid = `u_wx_${clientUuid.substring(0, 8)}`;
      const profile: UserProfile = {
        id: uid,
        display_name: `微信跑者_${clientUuid.substring(2, 6)}`,
        avatar_url: "",
        garmin_connected: false,
        garmin_email: "",
        garmin_domain: "garmin.cn",
      };
      setSession("local_token", profile);
      return profile;
    };

    const safeResolve = (user: UserProfile | null) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(safetyTimer);
      resolve(user);
    };

    // Hard safety timer: guarantee resolution within 3 seconds
    const safetyTimer = setTimeout(() => {
      console.warn("[wechatLogin] Safety timeout hit, resolving fallback user");
      safeResolve(fallbackUser());
    }, 3000);

    const doBackendLogin = async (code: string) => {
      try {
        const data = await request("/api/auth/wechat/miniapp-login", "POST", {
          code: code,
          client_uuid: clientUuid,
        });

        const uid = data.uid || `user_${clientUuid.substring(0, 8)}`;
        const profile: UserProfile = {
          id: uid,
          display_name: data.display_name || "微信跑者",
          avatar_url: data.avatar_url || "",
          garmin_connected: Boolean(data.garmin_connected),
          garmin_email: data.garmin_email || "",
          garmin_domain: data.garmin_domain || "garmin.cn",
        };

        setSession(data.token || "rgm_token", profile);
        console.log("[wechatLogin] User session saved:", profile);
        safeResolve(profile);
      } catch (e: any) {
        console.warn("[wechatLogin] Backend login network fallback:", e);
        const fb = fallbackUser();
        safeResolve(fb);
      }
    };

    // Use uni.login as the primary standard method
    uni.login({
      provider: "weixin",
      timeout: 10000,
      success: (loginRes: any) => {
        if (loginRes && loginRes.code) {
          doBackendLogin(loginRes.code);
        } else {
          safeResolve(fallbackUser());
        }
      },
      fail: (err: any) => {
        console.warn("[wechatLogin] uni.login fail, trying wx.login:", err);
        if (typeof wx !== "undefined" && typeof wx.login === "function") {
          wx.login({
            success: (res: any) => {
              if (res && res.code) {
                doBackendLogin(res.code);
              } else {
                safeResolve(fallbackUser());
              }
            },
            fail: () => safeResolve(fallbackUser()),
          });
        } else {
          safeResolve(fallbackUser());
        }
      },
    });
  });
}

/**
 * Returns stored user if available; does NOT create new user automatically.
 */
export function checkAndAutoLogin(): UserProfile | null {
  return getStoredUser();
}

/**
 * Authentic WeChat Login:
 * Authenticates current user via wx.login, guarantees isolated UID and data.
 * No user can ever select or impersonate another user's account.
 */
export async function authenticateWechatUser(options?: {
  nickName?: string;
  avatarUrl?: string;
  agreeTerms?: boolean;
}): Promise<UserProfile> {
  let clientUuid = uni.getStorageSync("rgm_client_uuid");
  if (!clientUuid) {
    clientUuid = "c_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
    uni.setStorageSync("rgm_client_uuid", clientUuid);
  }

  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      timeout: 10000,
      success: async (loginRes: any) => {
        try {
          const code = loginRes?.code || "";
          const data = await request("/api/auth/wechat/miniapp-login", "POST", {
            code: code,
            client_uuid: clientUuid,
            nick_name: options?.nickName || undefined,
            avatar_url: options?.avatarUrl || undefined,
          });

          const uid = data.uid || data.user?.id;
          const profile: UserProfile = {
            id: uid,
            display_name: data.display_name || data.user?.display_name || "微信跑者",
            avatar_url: data.avatar_url || data.user?.avatar_url || "",
            garmin_connected: Boolean(data.garmin_connected || data.user?.garmin_connected),
            garmin_email: data.garmin_email || data.user?.garmin_email || "",
            garmin_domain: data.garmin_domain || data.user?.garmin_domain || "garmin.cn",
            coros_connected: Boolean(data.coros_connected || data.user?.coros_connected),
            coros_account: data.coros_account || data.user?.coros_account || "",
            coros_domain: data.coros_domain || data.user?.coros_domain || "teamcnapi.coros.com",
          };

          setSession(data.token, profile);
          resolve(profile);
        } catch (err) {
          reject(err);
        }
      },
      fail: async () => {
        try {
          const data = await request("/api/auth/wechat/miniapp-login", "POST", {
            code: "",
            client_uuid: clientUuid,
            nick_name: options?.nickName || undefined,
            avatar_url: options?.avatarUrl || undefined,
          });
          const uid = data.uid || data.user?.id;
          const profile: UserProfile = {
            id: uid,
            display_name: data.display_name || data.user?.display_name || "微信跑者",
            avatar_url: data.avatar_url || data.user?.avatar_url || "",
            garmin_connected: Boolean(data.garmin_connected || data.user?.garmin_connected),
            garmin_email: data.garmin_email || data.user?.garmin_email || "",
            garmin_domain: data.garmin_domain || data.user?.garmin_domain || "garmin.cn",
            coros_connected: Boolean(data.coros_connected || data.user?.coros_connected),
            coros_account: data.coros_account || data.user?.coros_account || "",
            coros_domain: data.coros_domain || data.user?.coros_domain || "teamcnapi.coros.com",
          };
          setSession(data.token, profile);
          resolve(profile);
        } catch (e) {
          reject(e);
        }
      },
    });
  });
}

// Backward compatibility aliases
export const confirmWechatLogin = authenticateWechatUser;
export async function getAvailableUsers(): Promise<any[]> {
  return [];
}

export async function switchAccount(_targetUid: string): Promise<UserProfile> {
  throw new Error("安全保护：已禁止任意切换账号");
}

/**
 * Log in / recover account via Garmin or COROS credentials.
 */
export async function deviceLogin(params: {
  brand: string;
  account: string;
  password: string;
  domain?: string;
  mfa_code?: string;
}): Promise<UserProfile> {
  let clientUuid = uni.getStorageSync("rgm_client_uuid");
  let code = "";
  try {
    const loginRes: any = await new Promise((resolve) => {
      uni.login({
        provider: "weixin",
        timeout: 5000,
        success: resolve,
        fail: () => resolve(null),
      });
    });
    if (loginRes && loginRes.code) {
      code = loginRes.code;
    }
  } catch (e) {}

  const data = await request("/api/auth/device-login", "POST", {
    ...params,
    code: code,
    client_uuid: clientUuid,
  });
  const profile: UserProfile = {
    id: data.uid,
    display_name: data.display_name || "微信跑者",
    avatar_url: data.avatar_url || "",
    garmin_connected: Boolean(data.garmin_connected),
    garmin_email: data.garmin_email || "",
    garmin_domain: data.garmin_domain || "garmin.cn",
    coros_connected: Boolean(data.coros_connected),
    coros_account: data.coros_account || "",
    coros_domain: data.coros_domain || "teamcnapi.coros.com",
  };
  setSession(data.token, profile);
  return profile;
}

/**
 * Binds COROS (高驰) account.
 */
export async function bindCoros(payload: {
  uid: string;
  account: string;
  password: string;
  domain?: string;
}): Promise<any> {
  return request("/api/auth/coros/bind", "POST", {
    uid: payload.uid,
    account: payload.account,
    password: payload.password,
    domain: payload.domain || "teamcnapi.coros.com",
  });
}

/**
 * Unbinds COROS (高驰) account.
 */
export async function unbindCoros(uid: string): Promise<any> {
  return request("/api/auth/coros/unbind", "POST", { uid });
}

/**
 * Uploads an avatar image (tempFilePath from chooseAvatar or chooseImage) to the server.
 * Uses Base64 via standard request() so it relies on request合法域名 (bypasses uploadFile domain restrictions).
 * Falls back to uni.uploadFile if Base64 read is unavailable.
 */
export async function uploadAvatarFile(uid: string, tempFilePath: string): Promise<string> {
  if (!uid) throw new Error("缺少用户 UID");
  if (!tempFilePath) throw new Error("缺少头像文件路径");

  // 1. Primary: Read file as Base64 and POST via standard request
  try {
    const base64Data = await new Promise<string>((resolve, reject) => {
      // #ifdef MP-WEIXIN
      try {
        const fs = uni.getFileSystemManager();
        fs.readFile({
          filePath: tempFilePath,
          encoding: "base64",
          success: (res) => {
            if (res.data) resolve(res.data as string);
            else reject(new Error("读取头像内容为空"));
          },
          fail: (err) => reject(err),
        });
      } catch (e) {
        reject(e);
      }
      // #endif
      // #ifndef MP-WEIXIN
      reject(new Error("非微信小程序环境"));
      // #endif
    });

    const res = await request(`/api/profile/${encodeURIComponent(uid)}/avatar-base64`, "POST", {
      image_base64: base64Data,
      ext: ".jpg",
    });

    if (res && res.avatar_url) {
      return res.avatar_url;
    }
    throw new Error(res?.detail || "上传未返回头像地址");
  } catch (b64Err) {
    console.warn("Base64 upload error, trying uploadFile fallback:", b64Err);

    // 2. Fallback: uni.uploadFile with encoded URL
    return new Promise<string>((resolve, reject) => {
      const token = uni.getStorageSync("rgm_token");
      uni.uploadFile({
        url: `${API_BASE_URL}/api/profile/${encodeURIComponent(uid)}/avatar`,
        filePath: tempFilePath,
        name: "file",
        header: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        success: (uploadRes) => {
          try {
            const data = typeof uploadRes.data === "string" ? JSON.parse(uploadRes.data) : uploadRes.data;
            if (data.avatar_url) {
              resolve(data.avatar_url);
            } else {
              reject(new Error(data.detail || "上传未返回头像地址"));
            }
          } catch (e) {
            reject(new Error("解析上传响应失败"));
          }
        },
        fail: (err) => {
          console.error("uploadFile fail:", err);
          reject(new Error(err?.errMsg || "头像上传失败"));
        },
      });
    });
  }
}

/**
 * Helper to update custom tabBar selected index on page onShow
 */
export function syncTabBarIndex(index: number) {
  try {
    const pages = getCurrentPages();
    if (pages && pages.length) {
      const cur = pages[pages.length - 1] as any;
      if (cur && typeof cur.getTabBar === "function") {
        const tb = cur.getTabBar();
        if (tb && typeof tb.setData === "function") {
          tb.setData({ selected: index });
        }
      }
    }
  } catch (e) {
    // Ignore in non-tab contexts
  }
}
