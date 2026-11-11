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
  coros_needs_reauth?: boolean;
  apple_watch_connected?: boolean;
  huawei_connected?: boolean;
  huawei_account?: string;
  suunto_connected?: boolean;
  suunto_account?: string;
  max_heart_rate?: number;
  resting_heart_rate?: number;
  vo2max?: number;
  marathon_pb?: number;
  role?: string;
  is_coach_or_owner?: boolean;
  is_admin?: boolean;
}

export function getToken(): string {
  const token = uni.getStorageSync("rgm_token") || "";
  if (token === "local_token") return "";
  return token;
}

/**
 * Returns current logged-in user profile from local storage, or null if not logged in.
 * STRICTLY NO HARDCODED DEFAULT USER.
 */
export function getStoredUser(): UserProfile | null {
  if (uni.getStorageSync("rgm_token") === "local_token") {
    clearSession();
    return null;
  }
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
  uni.removeStorageSync("rgm_is_coach_or_owner");
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
  try {
    uni.setStorageSync("rgm_dashboard_dirty", 1);
  } catch (_) {}
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

type ApiTelemetryReporter = (
  url: string,
  method: string,
  statusOrErr: number | string,
  durationMs: number
) => void;

let _apiTelemetryReporter: ApiTelemetryReporter | null = null;

export function registerApiTelemetryReporter(fn: ApiTelemetryReporter) {
  _apiTelemetryReporter = fn;
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
  const storedUid = getStoredUser()?.id || "";
  const fullUrl = url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
  const reqStartedAt = Date.now();

  return new Promise((resolve, reject) => {
    uni.request({
      url: fullUrl,
      method,
      data,
      timeout: 90000,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(storedUid ? { "x-user-id": storedUid } : {}),
      },
      success: (res) => {
        const elapsedMs = Date.now() - reqStartedAt;
        if (res.statusCode >= 200 && res.statusCode < 300) {
          if (elapsedMs >= 3500 && _apiTelemetryReporter) {
            try {
              _apiTelemetryReporter(url, method, res.statusCode, elapsedMs);
            } catch (_) {}
          }
          try {
            const d: any = res.data;
            if (d && typeof d === "object") {
              if (typeof d.user?.is_coach_or_owner === "boolean") {
                updateCoachOrOwnerRole(d.user.is_coach_or_owner);
              } else if (typeof d.profile?.is_coach_or_owner === "boolean") {
                updateCoachOrOwnerRole(d.profile.is_coach_or_owner);
              } else if (typeof d.is_coach_or_owner === "boolean") {
                updateCoachOrOwnerRole(d.is_coach_or_owner);
              } else if (url.includes("/api/team/my-clubs/") && Array.isArray(d.clubs)) {
                const hasCoachRole = d.clubs.some(
                  (c: any) => c.role === "owner" || c.role === "coach" || c.role === "admin"
                );
                updateCoachOrOwnerRole(hasCoachRole);
              }
            }
          } catch (_) {}
          if (method && method.toUpperCase() !== "GET" && !url.includes("/notifications/read")) {
            try {
              uni.setStorageSync("rgm_dashboard_dirty", 1);
            } catch (_) {}
          }
          resolve(res.data as T);
        } else if (res.statusCode === 401) {
          clearSession();
          uni.showToast({ title: "登录已失效，正在重新登录", icon: "none" });
          reject(new Error("Unauthorized"));
        } else {
          let rawErr = (res.data as any)?.detail || (res.data as any)?.message || (res.data as any)?.error;
          let errMsg = "";
          if (Array.isArray(rawErr)) {
            errMsg = rawErr.map((item: any) => {
              if (typeof item === "string") return item;
              if (item?.msg) {
                const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : "";
                return field ? `${field}: ${item.msg}` : item.msg;
              }
              return JSON.stringify(item);
            }).join("; ");
          } else if (typeof rawErr === "object" && rawErr !== null) {
            errMsg = rawErr.message || rawErr.msg || JSON.stringify(rawErr);
          } else if (rawErr) {
            errMsg = String(rawErr);
          }
          if (!errMsg) {
            errMsg = `请求失败 (${res.statusCode})`;
          }
          const err = new Error(errMsg);
          (err as any).data = res.data;
          (err as any).statusCode = res.statusCode;
          if (_apiTelemetryReporter) {
            try {
              _apiTelemetryReporter(url, method, `${res.statusCode}: ${errMsg.slice(0, 60)}`, elapsedMs);
            } catch (_) {}
          }
          reject(err);
        }
      },
      fail: (err) => {
        const elapsedMs = Date.now() - reqStartedAt;
        if (_apiTelemetryReporter) {
          try {
            _apiTelemetryReporter(url, method, err?.errMsg || "network_fail", elapsedMs);
          } catch (_) {}
        }
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

export function getPendingInviterUid(): string {
  return uni.getStorageSync("rgm_pending_inviter_uid") || "";
}

export function setPendingInviterUid(inviterUid?: string) {
  const clean = (inviterUid || "").trim();
  if (!clean) return;
  const current = getStoredUser();
  if (current && current.id === clean) return;
  uni.setStorageSync("rgm_pending_inviter_uid", clean);
}

export function clearPendingInviterUid() {
  uni.removeStorageSync("rgm_pending_inviter_uid");
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
      if (!forceNew) {
        const existing = getStoredUser();
        if (existing && existing.id) {
          return existing;
        }
      }
      const uid = `u_wx_${clientUuid.substring(0, 8)}`;
      const profile: UserProfile = {
        id: uid,
        display_name: `微信跑者_${clientUuid.substring(2, 6)}`,
        avatar_url: "",
        garmin_connected: false,
        garmin_email: "",
        garmin_domain: "garmin.cn",
      };
      // Transient in-memory guest fallback only; never poison persistent storage with "local_token"
      return profile;
    };

    const safeResolve = (user: UserProfile | null) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(safetyTimer);
      resolve(user);
    };

    // Hard safety timer: guarantee resolution within 15 seconds on weak outdoor mobile networks
    const safetyTimer = setTimeout(() => {
      console.warn("[wechatLogin] Safety timeout hit, resolving transient fallback user");
      safeResolve(fallbackUser());
    }, 15000);

    const doBackendLogin = async (code: string) => {
      try {
        const inviterUid = getPendingInviterUid();
        const data = await request("/api/auth/wechat/miniapp-login", "POST", {
          code: code,
          client_uuid: clientUuid,
          inviter_uid: inviterUid || undefined,
        });
        if (inviterUid) clearPendingInviterUid();

        const uid = data.uid || `user_${clientUuid.substring(0, 8)}`;
        const profile: UserProfile = {
          id: uid,
          display_name: data.display_name || "微信跑者",
          avatar_url: data.avatar_url || "",
          garmin_connected: Boolean(data.garmin_connected),
          garmin_email: data.garmin_email || "",
          garmin_domain: data.garmin_domain || "garmin.cn",
          coros_connected: Boolean(data.coros_connected),
          coros_account: data.coros_account || "",
          coros_domain: data.coros_domain || "teamcnapi.coros.com",
          apple_watch_connected: Boolean(data.apple_watch_connected),
          huawei_connected: Boolean(data.huawei_connected),
          huawei_account: data.huawei_account || "",
          suunto_connected: Boolean(data.suunto_connected),
          suunto_account: data.suunto_account || "",
          is_coach_or_owner: Boolean(data.is_coach_or_owner),
          is_admin: Boolean(data.is_admin),
        };

        if (data.token && data.token !== "local_token") {
          setSession(data.token, profile);
        }
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
 * Silently checks if the current WeChat user already has an RGM account (by openid).
 * - If existing account found: links profile & restores session immediately.
 * - If brand-new visitor: returns null WITHOUT creating an account until they tap Join.
 */
export async function silentCheckExistingWechatUser(): Promise<UserProfile | null> {
  const existing = getStoredUser();
  if (existing && existing.id && existing.id !== "runner_001") {
    return existing;
  }
  let clientUuid = uni.getStorageSync("rgm_client_uuid");
  if (!clientUuid) {
    clientUuid = "c_" + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
    uni.setStorageSync("rgm_client_uuid", clientUuid);
  }
  return new Promise((resolve) => {
    uni.login({
      provider: "weixin",
      timeout: 6000,
      success: async (loginRes: any) => {
        try {
          const code = loginRes?.code || "";
          if (!code) {
            resolve(null);
            return;
          }
          const data: any = await request("/api/auth/wechat/miniapp-login", "POST", {
            code,
            client_uuid: clientUuid,
            check_only: true,
          });
          if (data?.found_existing && data?.uid && data?.token) {
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
              apple_watch_connected: Boolean(data.apple_watch_connected),
              huawei_connected: Boolean(data.huawei_connected),
              huawei_account: data.huawei_account || "",
              suunto_connected: Boolean(data.suunto_connected),
              suunto_account: data.suunto_account || "",
              is_coach_or_owner: Boolean(data.is_coach_or_owner),
              is_admin: Boolean(data.is_admin),
            };
            setSession(data.token, profile);
            resolve(profile);
            return;
          }
          resolve(null);
        } catch (_) {
          resolve(null);
        }
      },
      fail: () => resolve(null),
    });
  });
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
  const inviterUid = getPendingInviterUid();

  return new Promise((resolve, reject) => {
    uni.login({
      provider: "weixin",
      timeout: 10000,
      success: async (loginRes: any) => {
        try {
          let data: any;
          // #ifdef APP-PLUS
          const authResult = loginRes?.authResult || {};
          data = await request("/api/auth/app/wechat-login", "POST", {
            code: loginRes?.code || undefined,
            unionid: authResult.unionid || undefined,
            openid: authResult.openid || undefined,
            access_token: authResult.access_token || undefined,
            client_uuid: clientUuid,
            nick_name: options?.nickName || undefined,
            avatar_url: options?.avatarUrl || undefined,
            inviter_uid: inviterUid || undefined,
          });
          // #endif
          // #ifndef APP-PLUS
          const code = loginRes?.code || "";
          data = await request("/api/auth/wechat/miniapp-login", "POST", {
            code: code,
            client_uuid: clientUuid,
            nick_name: options?.nickName || undefined,
            avatar_url: options?.avatarUrl || undefined,
            inviter_uid: inviterUid || undefined,
          });
          // #endif
          if (inviterUid) clearPendingInviterUid();

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
            apple_watch_connected: Boolean(data.apple_watch_connected || data.user?.apple_watch_connected),
            huawei_connected: Boolean(data.huawei_connected || data.user?.huawei_connected),
            huawei_account: data.huawei_account || data.user?.huawei_account || "",
            suunto_connected: Boolean(data.suunto_connected || data.user?.suunto_connected),
            suunto_account: data.suunto_account || data.user?.suunto_account || "",
            is_coach_or_owner: Boolean(data.is_coach_or_owner || data.user?.is_coach_or_owner),
            is_admin: Boolean(data.is_admin || data.user?.is_admin),
          };

          setSession(data.token, profile);
          resolve(profile);
        } catch (err) {
          reject(err);
        }
      },
      fail: async (err: any) => {
        try {
          const data = await request("/api/auth/wechat/miniapp-login", "POST", {
            code: "",
            client_uuid: clientUuid,
            nick_name: options?.nickName || undefined,
            avatar_url: options?.avatarUrl || undefined,
            inviter_uid: inviterUid || undefined,
          });
          if (inviterUid) clearPendingInviterUid();
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
            apple_watch_connected: Boolean(data.apple_watch_connected || data.user?.apple_watch_connected),
            huawei_connected: Boolean(data.huawei_connected || data.user?.huawei_connected),
            huawei_account: data.huawei_account || data.user?.huawei_account || "",
            suunto_connected: Boolean(data.suunto_connected || data.user?.suunto_connected),
            suunto_account: data.suunto_account || data.user?.suunto_account || "",
            is_coach_or_owner: Boolean(data.is_coach_or_owner || data.user?.is_coach_or_owner),
            is_admin: Boolean(data.is_admin || data.user?.is_admin),
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

/**
 * Sign in with Apple (Mandatory for iOS App Store)
 */
export async function authenticateAppleUser(): Promise<UserProfile> {
  return new Promise((resolve, reject) => {
    // #ifdef APP-PLUS
    uni.login({
      provider: "apple",
      timeout: 15000,
      success: async (loginRes: any) => {
        try {
          const authResult = loginRes?.authResult || {};
          const appleUserId = authResult.userInfo?.openId || authResult.openId || "";
          let fullName: string | undefined = undefined;
          if (authResult.userInfo?.fullName) {
            const fn = authResult.userInfo.fullName;
            fullName = `${fn.familyName || ""}${fn.givenName || ""}`.trim() || undefined;
          }
          const email = authResult.userInfo?.email || undefined;

          if (!appleUserId) {
            throw new Error("未能获取有效的 Apple ID 授权凭据");
          }

          const data = await request("/api/auth/apple/login", "POST", {
            apple_user_id: appleUserId,
            identity_token: authResult.identityToken,
            email: email,
            full_name: fullName,
          });

          const uid = data.uid || data.user?.id;
          const profile: UserProfile = {
            id: uid,
            display_name: data.display_name || data.user?.display_name || "Apple跑者",
            avatar_url: data.avatar_url || data.user?.avatar_url || "",
            garmin_connected: Boolean(data.garmin_connected || data.user?.garmin_connected),
            garmin_email: data.garmin_email || data.user?.garmin_email || "",
            garmin_domain: data.garmin_domain || data.user?.garmin_domain || "garmin.cn",
            coros_connected: Boolean(data.coros_connected || data.user?.coros_connected),
            coros_account: data.coros_account || data.user?.coros_account || "",
            coros_domain: data.coros_domain || data.user?.coros_domain || "teamcnapi.coros.com",
            apple_watch_connected: Boolean(data.apple_watch_connected || data.user?.apple_watch_connected),
            huawei_connected: Boolean(data.huawei_connected || data.user?.huawei_connected),
            huawei_account: data.huawei_account || data.user?.huawei_account || "",
            suunto_connected: Boolean(data.suunto_connected || data.user?.suunto_connected),
            suunto_account: data.suunto_account || data.user?.suunto_account || "",
            is_coach_or_owner: Boolean(data.is_coach_or_owner || data.user?.is_coach_or_owner),
            is_admin: Boolean(data.is_admin || data.user?.is_admin),
          };

          setSession(data.token, profile);
          resolve(profile);
        } catch (err) {
          reject(err);
        }
      },
      fail: (err: any) => {
        reject(new Error(err?.errMsg || "Apple 登录取消或失败"));
      },
    });
    // #endif
    // #ifndef APP-PLUS
    reject(new Error("Apple 登录仅在 iOS App 客户端可用"));
    // #endif
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
  if (data?.needs_2fa || data?.needs_mfa) {
    return {
      needs_2fa: true,
      needs_mfa: true,
      message: data.message || "官方已发送 6 位安全验证码，请输入验证码完成登录",
    } as any;
  }
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
    apple_watch_connected: Boolean(data.apple_watch_connected),
    huawei_connected: Boolean(data.huawei_connected),
    huawei_account: data.huawei_account || "",
    suunto_connected: Boolean(data.suunto_connected),
    suunto_account: data.suunto_account || "",
    is_coach_or_owner: Boolean(data.is_coach_or_owner),
    is_admin: Boolean(data.user?.is_admin),
  };
  setSession(data.token, profile);
  return profile;
}

/**
 * Marks a Web WeChat Mini-Program QR login session as scanned.
 */
export async function scanWebQrLogin(sceneId: string, displayName?: string, avatarUrl?: string): Promise<any> {
  return request("/api/auth/wechat/web-qr/scan", "POST", {
    scene_id: sceneId,
    display_name: displayName || "",
    avatar_url: avatarUrl || "",
  });
}

/**
 * Confirms a Web WeChat Mini-Program QR login session using current Mini-Program JWT (or fresh wx.login code).
 */
export async function confirmWebQrLogin(sceneId: string, displayName?: string, avatarUrl?: string): Promise<any> {
  let code = "";
  if (!getToken()) {
    try {
      const loginRes: any = await new Promise((resolve) => {
        uni.login({
          provider: "weixin",
          timeout: 5000,
          success: resolve,
          fail: () => resolve(null),
        });
      });
      if (loginRes?.code) code = loginRes.code;
    } catch (e) {}
  }
  return request("/api/auth/wechat/web-qr/confirm", "POST", {
    scene_id: sceneId,
    code: code || undefined,
    display_name: displayName || "",
    avatar_url: avatarUrl || "",
  });
}

/**
 * Binds COROS (高驰) account.
 */
export async function bindCoros(payload: {
  uid: string;
  account: string;
  password?: string;
  domain?: string;
  code?: string;
  mfa_code?: string;
}): Promise<any> {
  const inviterUid = getPendingInviterUid();
  return request("/api/auth/coros/bind", "POST", {
    uid: payload.uid,
    account: payload.account,
    password: payload.password || "",
    domain: payload.domain || "teamcnapi.coros.com",
    code: payload.code || payload.mfa_code,
    inviter_uid: inviterUid || undefined,
  });
}

/**
 * Unbinds COROS (高驰) account.
 */
export async function unbindCoros(uid: string): Promise<any> {
  return request("/api/auth/coros/unbind", "POST", { uid });
}

/**
 * Binds Apple Watch, Huawei Watch, or Suunto Watch on the user's profile.
 */
export async function bindHealthWatch(
  uid: string,
  brand: "apple_watch" | "huawei" | "suunto",
  account?: string
): Promise<any> {
  const path =
    brand === "apple_watch"
      ? "/api/auth/apple-watch/bind"
      : brand === "suunto"
      ? "/api/auth/suunto/bind"
      : "/api/auth/huawei/bind";
  const inviterUid = getPendingInviterUid();
  const body: any = { uid, inviter_uid: inviterUid || undefined };
  if (account) body.account = account;
  return request(path, "POST", body);
}

/**
 * Unbinds Apple Watch, Huawei Watch, or Suunto Watch from the user's profile.
 */
export async function unbindHealthWatch(
  uid: string,
  brand: "apple_watch" | "huawei" | "suunto"
): Promise<any> {
  const path =
    brand === "apple_watch"
      ? "/api/auth/apple-watch/unbind"
      : brand === "suunto"
      ? "/api/auth/suunto/unbind"
      : "/api/auth/huawei/unbind";
  return request(path, "POST", { uid });
}

/**
 * Imports a FIT, GPX, or TCX track file (Base64 encoded) exported from Huawei Health, Suunto App, or Apple Watch.
 */
export async function importTrackFileBase64(params: {
  uid: string;
  filename: string;
  content_base64: string;
  source_brand: "apple_watch" | "huawei" | "suunto";
}): Promise<any> {
  return request("/api/sync/import-track-file", "POST", params);
}

/**
 * Opens WeChat message file picker to choose a .fit / .gpx / .tcx / .xml / .gz trajectory file
 * and uploads it to the server via Base64.
 */
export async function chooseAndImportTrackFile(
  uid: string,
  sourceBrand: "apple_watch" | "huawei" | "suunto" = "huawei"
): Promise<any> {
  if (!uid) throw new Error("请先登录账号");

  const pickedFile = await new Promise<{ path: string; name: string }>((resolve, reject) => {
    const pickerFn =
      typeof wx !== "undefined" && typeof wx.chooseMessageFile === "function"
        ? wx.chooseMessageFile.bind(wx)
        : typeof (uni as any).chooseMessageFile === "function"
        ? (uni as any).chooseMessageFile.bind(uni)
        : null;

    if (pickerFn) {
      pickerFn({
        count: 1,
        type: "file",
        extension: ["fit", "gpx", "tcx", "xml", "gz", "FIT", "GPX", "TCX", "XML", "GZ"],
        success: (res: any) => {
          const f = res?.tempFiles?.[0];
          if (f && f.path) {
            resolve({ path: f.path, name: f.name || "workout.gpx" });
          } else {
            reject(new Error("未选择有效的轨迹文件"));
          }
        },
        fail: (err: any) => {
          const msg = err?.errMsg || "";
          if (msg.includes("cancel")) {
            reject(new Error("__CANCEL__"));
          } else {
            reject(new Error("未能打开微信聊天文件选择，请先将 FIT/GPX/TCX 文件发送到微信「文件传输助手」"));
          }
        },
      });
      return;
    }

    if (typeof (uni as any).chooseFile === "function") {
      (uni as any).chooseFile({
        count: 1,
        extension: [".fit", ".gpx", ".tcx", ".xml", ".gz"],
        success: (res: any) => {
          const f = res?.tempFiles?.[0];
          const path = f?.path || res?.tempFilePaths?.[0];
          if (path) {
            resolve({ path, name: f?.name || "workout.gpx" });
          } else {
            reject(new Error("未选择有效的轨迹文件"));
          }
        },
        fail: (err: any) => {
          const msg = err?.errMsg || "";
          if (msg.includes("cancel")) {
            reject(new Error("__CANCEL__"));
          } else {
            reject(new Error("未选择轨迹文件"));
          }
        },
      });
      return;
    }

    reject(new Error("当前环境暂不支持直接读取文件，请先将 GPX/TCX 发送至微信聊天后在小程序中导入"));
  });

  const base64Data = await new Promise<string>((resolve, reject) => {
    try {
      const fs = uni.getFileSystemManager();
      fs.readFile({
        filePath: pickedFile.path,
        encoding: "base64",
        success: (res: any) => {
          if (res?.data && typeof res.data === "string") {
            resolve(res.data);
          } else {
            reject(new Error("轨迹文件内容为空"));
          }
        },
        fail: (err: any) => {
          reject(new Error(err?.errMsg || "读取轨迹文件失败"));
        },
      });
    } catch (e: any) {
      reject(new Error(e?.message || "读取轨迹文件失败"));
    }
  });

  return importTrackFileBase64({
    uid,
    filename: pickedFile.name,
    content_base64: base64Data,
    source_brand: sourceBrand,
  });
}

/**
 * Picks 1-3 workout/Apple Health/Huawei Health/Suunto App screenshots from album and imports all recognized running records.
 * Supports multi-day Apple Health list screenshots ("所有已记录的数据") as well as single workout screenshots.
 */
export async function chooseAndImportScreenshot(
  uid: string,
  sourceBrand: "apple_watch" | "huawei" | "suunto" = "huawei"
): Promise<any> {
  if (!uid) throw new Error("请先登录账号");

  const pickedPaths = await new Promise<string[]>((resolve, reject) => {
    const fallbackChooseImg = () => {
      uni.chooseImage({
        count: 3,
        sizeType: ["compressed", "original"],
        sourceType: ["album", "camera"],
        success: (res: any) => {
          const paths: string[] = res?.tempFilePaths || [];
          if (paths.length > 0) {
            resolve(paths);
          } else {
            reject(new Error("未选择有效的运动截图"));
          }
        },
        fail: (err: any) => {
          const msg = err?.errMsg || "";
          if (msg.includes("cancel")) {
            reject(new Error("__CANCEL__"));
          } else {
            reject(new Error("未选择运动截图"));
          }
        },
      });
    };

    // #ifdef MP-WEIXIN
    if (typeof uni.chooseMedia === "function") {
      uni.chooseMedia({
        count: 3,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        sizeType: ["compressed", "original"],
        success: (res: any) => {
          const files = res?.tempFiles || [];
          const paths = files.map((f: any) => f.tempFilePath).filter(Boolean);
          if (paths.length > 0) {
            resolve(paths);
          } else {
            reject(new Error("未选择有效的运动截图"));
          }
        },
        fail: (err: any) => {
          const msg = err?.errMsg || "";
          if (msg.includes("cancel")) {
            reject(new Error("__CANCEL__"));
          } else {
            fallbackChooseImg();
          }
        },
      });
      return;
    }
    // #endif
    fallbackChooseImg();
  });

  uni.showLoading({
    title: pickedPaths.length > 1 ? `正在解析 ${pickedPaths.length} 张截图...` : "正在解析运动截图...",
    mask: true,
  });

  try {
    let totalImported = 0;
    let totalSkipped = 0;
    let totalRecognized = 0;
    let totalKm = 0;
    const allRecords: any[] = [];
    let lastMsg = "";

    for (let i = 0; i < pickedPaths.length; i++) {
      const rawPath = pickedPaths[i];
      let readyPath = rawPath;
      try {
        readyPath = await compressImageIfPossible(rawPath, 82, 1600);
      } catch (_) {}

      let singleRes: any = null;
      try {
        const b64 = await new Promise<string>((resolve, reject) => {
          try {
            const fs = uni.getFileSystemManager();
            fs.readFile({
              filePath: readyPath,
              encoding: "base64",
              success: (r: any) => {
                if (r?.data && typeof r.data === "string") resolve(r.data);
                else reject(new Error("读取截图内容为空"));
              },
              fail: (err: any) => reject(new Error(err?.errMsg || "读取截图失败")),
            });
          } catch (e: any) {
            reject(new Error(e?.message || "读取截图失败"));
          }
        });

        singleRes = await request("/api/sync/import-screenshot", "POST", {
          uid,
          image_base64: b64,
          filename: `screenshot_${i + 1}.jpg`,
          source_brand: sourceBrand,
        });
      } catch (b64Err: any) {
        // If server returned an explicit 400 validation error, rethrow immediately
        if (b64Err?.statusCode === 400) {
          throw b64Err;
        }
        // Fallback to multipart uploadFile
        singleRes = await new Promise<any>((resolve, reject) => {
          const token = getToken();
          uni.uploadFile({
            url: `${API_BASE_URL}/api/sync/import-screenshot-upload`,
            filePath: readyPath,
            name: "file",
            formData: {
              uid,
              source_brand: sourceBrand,
            },
            header: {
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            success: (upRes) => {
              try {
                const parsed = typeof upRes.data === "string" ? JSON.parse(upRes.data) : upRes.data;
                if (upRes.statusCode >= 200 && upRes.statusCode < 300) {
                  resolve(parsed);
                } else {
                  reject(new Error(parsed?.detail || parsed?.message || "解析截图失败"));
                }
              } catch (_) {
                reject(new Error("解析截图响应失败"));
              }
            },
            fail: (err) => {
              reject(new Error(b64Err?.message || err?.errMsg || "上传截图失败"));
            },
          });
        });
      }

      if (singleRes && singleRes.success) {
        totalImported += Number(singleRes.imported || 0);
        totalSkipped += Number(singleRes.skipped_duplicates || 0);
        totalRecognized += Number(singleRes.total_recognized || 0);
        totalKm += Number(singleRes.total_distance_km || 0);
        if (Array.isArray(singleRes.records)) {
          allRecords.push(...singleRes.records);
        }
        lastMsg = singleRes.message || lastMsg;
      }
    }

    const summaryMsg =
      pickedPaths.length === 1 && lastMsg
        ? lastMsg
        : totalImported > 0
        ? `成功识别并导入 ${totalImported} 条跑步记录（累计 ${totalKm.toFixed(1)} km）✓`
        : `识别到 ${totalRecognized} 条跑步记录，均已存在无需重复导入 ✓`;

    return {
      success: true,
      status: "success",
      imported: totalImported,
      skipped_duplicates: totalSkipped,
      total_recognized: totalRecognized,
      total_distance_km: Number(totalKm.toFixed(2)),
      records: allRecords,
      message: summaryMsg,
    };
  } finally {
    uni.hideLoading();
  }
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
 * Automatically compress image file in WeChat Mini Program before Base64 encoding.
 * Reduces 5MB-10MB mobile phone camera pictures down to ~150-250KB for rapid, fail-safe transfer.
 */
export async function compressImageIfPossible(
  tempFilePath: string,
  quality = 75,
  width = 1280
): Promise<string> {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    try {
      if (typeof uni.compressImage === "function") {
        uni.compressImage({
          src: tempFilePath,
          quality,
          compressedWidth: width,
          success: (res: any) => {
            if (res && res.tempFilePath) {
              resolve(res.tempFilePath);
            } else {
              resolve(tempFilePath);
            }
          },
          fail: (err: any) => {
            console.warn("[compressImage] failed, fallback to original:", err);
            resolve(tempFilePath);
          },
        });
        return;
      }
    } catch (e) {
      console.warn("[compressImage] exception:", e);
    }
    // #endif
    resolve(tempFilePath);
  });
}

/**
 * Uploads a finisher certificate or race photo (tempFilePath from chooseMedia or chooseImage) to the server.
 * Uses Base64 via standard request() so it relies on request合法域名 (bypasses uploadFile domain restrictions).
 * Automatically compresses high-resolution camera photos beforehand to prevent wx.request payload limits.
 * Falls back to uni.uploadFile if Base64 read is unavailable.
 */
export async function uploadRacePhoto(uid: string, raceId: string, tempFilePath: string): Promise<string> {
  if (!uid) throw new Error("缺少用户 UID");
  if (!tempFilePath) throw new Error("缺少照片文件路径");

  // Step 1: Compress high-res mobile photo to avoid out-of-memory or payload limit
  let readyFilePath = tempFilePath;
  try {
    readyFilePath = await compressImageIfPossible(tempFilePath, 75, 1280);
  } catch (compErr) {
    console.warn("compress error, using original file:", compErr);
  }

  // Step 2: Primary - Read file as Base64 and POST via standard request (uses request合法域名)
  try {
    const base64Data = await new Promise<string>((resolve, reject) => {
      // #ifdef MP-WEIXIN
      try {
        const fs = uni.getFileSystemManager();
        fs.readFile({
          filePath: readyFilePath,
          encoding: "base64",
          success: (res) => {
            if (res.data) resolve(res.data as string);
            else reject(new Error("读取照片内容为空"));
          },
          fail: (err) => reject(new Error(err?.errMsg || "读取本地图片失败")),
        });
      } catch (e: any) {
        reject(new Error(e?.message || "读取文件异常"));
      }
      // #endif
      // #ifndef MP-WEIXIN
      reject(new Error("非微信小程序环境"));
      // #endif
    });

    const res = await request(`/api/profile/${encodeURIComponent(uid)}/races/${encodeURIComponent(raceId)}/photo-base64`, "POST", {
      image_base64: base64Data,
      ext: ".jpg",
    });

    if (res && res.photo_url) {
      return res.photo_url;
    }
    throw new Error(res?.detail || "上传未返回照片地址");
  } catch (b64Err: any) {
    console.warn("Base64 upload error, trying uploadFile fallback:", b64Err);

    // Step 3: Fallback - uni.uploadFile with encoded URL
    return new Promise<string>((resolve, reject) => {
      const token = uni.getStorageSync("rgm_token");
      uni.uploadFile({
        url: `${API_BASE_URL}/api/profile/${encodeURIComponent(uid)}/races/${encodeURIComponent(raceId)}/photo`,
        filePath: readyFilePath,
        name: "file",
        header: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        success: (uploadRes) => {
          try {
            const data = typeof uploadRes.data === "string" ? JSON.parse(uploadRes.data) : uploadRes.data;
            if (data.photo_url) {
              resolve(data.photo_url);
            } else {
              reject(new Error(data.detail || "上传未返回照片地址"));
            }
          } catch (e) {
            reject(new Error("解析上传响应失败"));
          }
        },
        fail: (err) => {
          console.error("uploadFile fail:", err);
          const msg = b64Err?.message || err?.errMsg || "照片上传失败";
          reject(new Error(msg));
        },
      });
    });
  }
}

/**
 * Deletes a race photo from the race plan.
 */
export async function deleteRacePhoto(uid: string, raceId: string, photoUrl: string): Promise<any> {
  return request(
    `/api/profile/${encodeURIComponent(uid)}/races/${encodeURIComponent(raceId)}/photo?photo_url=${encodeURIComponent(photoUrl)}`,
    "DELETE"
  );
}

/**
 * Updates cached coach/owner role flag and refreshes custom tab bar if changed.
 */
export function updateCoachOrOwnerRole(isCoach: boolean) {
  try {
    const prev = uni.getStorageSync("rgm_is_coach_or_owner");
    if (prev !== isCoach) {
      uni.setStorageSync("rgm_is_coach_or_owner", isCoach);
      syncTabBarIndex();
    }
  } catch (e) {
    // ignore
  }
}

/**
 * Helper to update custom tabBar selected index and role-based tab list on page onShow
 */
export function syncTabBarIndex(_index?: number) {
  try {
    const pages = getCurrentPages();
    if (pages && pages.length) {
      const cur = pages[pages.length - 1] as any;
      if (cur && typeof cur.getTabBar === "function") {
        const tb = cur.getTabBar();
        if (tb) {
          if (typeof tb.syncTheme === "function") {
            tb.syncTheme();
          }
          if (typeof tb.syncSelected === "function") {
            tb.syncSelected();
          } else if (typeof tb.setData === "function" && typeof _index === "number") {
            const theme = uni.getStorageSync("rgm_theme") || "dark";
            tb.setData({ selected: _index, theme });
          }
        }
      }
    }
  } catch (e) {
    // Ignore in non-tab contexts
  }
}

/**
 * 临时隐藏 / 恢复自定义 TabBar。
 * 自定义 TabBar 渲染在页面之上，页面里的底部弹窗无论 z-index 多高都会被它盖住，
 * 所以弹窗打开时需要先隐藏 TabBar。非 Tab 页调用无副作用。
 */
export function setTabBarHidden(hidden: boolean) {
  try {
    const pages = getCurrentPages();
    const cur = pages && (pages[pages.length - 1] as any);
    const tb = cur && typeof cur.getTabBar === "function" ? cur.getTabBar() : null;
    if (tb && typeof tb.setData === "function") tb.setData({ hidden });
  } catch (e) {
    // ignore
  }
}

let _hasPromptedOrgReminderInSession = false;

export interface OrgReminderInfo {
  hasReminder: boolean;
  type: "suspended" | "temporary" | "none";
  firstOrg?: any;
  orgCount?: number;
  orgNames?: string;
  missingLabels?: string;
  remainingDays?: number;
  title?: string;
  content?: string;
  confirmText?: string;
  cancelText?: string;
}

export async function fetchOrgReminderInfo(uid: string): Promise<OrgReminderInfo> {
  try {
    const res = await request(`/api/org/my-orgs/${encodeURIComponent(uid)}`);
    const orgs: any[] = res?.organizations || [];

    // 1. Check suspended/expired
    const suspendedMemberships = orgs.filter(
      (o: any) => o.status === "expired" || o.status === "suspended" || o.is_suspended
    );
    if (suspendedMemberships.length > 0) {
      const firstOrg = suspendedMemberships[0];
      return {
        hasReminder: true,
        type: "suspended",
        firstOrg,
        orgCount: suspendedMemberships.length,
        orgNames: suspendedMemberships.map((o: any) => o.name).join("、"),
        title: "⚠️ 大群访问已被暂停",
        content: `您在【${firstOrg.name}】的2周临时访问期已过。由于超期未完成必填字段并获管理员审核确认，已暂停浏览使用该大群及其分队的一切内容和活动！请立即补齐必填资料并联系管理员核验。`,
        confirmText: "立即补齐",
        cancelText: "知道了",
      };
    }

    // 2. Check temporary with missing fields or any org where missing_fields is non-empty
    const incompleteMemberships = orgs.filter(
      (o: any) =>
        (o.missing_fields && o.missing_fields.length > 0) ||
        o.status === "temporary"
    );
    if (incompleteMemberships.length > 0) {
      const firstOrg = incompleteMemberships[0];
      const missingLabels = (firstOrg.missing_fields || []).map((f: any) => f.label || f.field).join("、");
      const orgCount = incompleteMemberships.length;
      const orgNames = incompleteMemberships.map((o: any) => o.name).join("、");
      const remainingDays =
        firstOrg.days_remaining !== undefined && firstOrg.days_remaining !== null
          ? firstOrg.days_remaining
          : 14;
      const contentText =
        orgCount > 1
          ? `您在 ${orgCount} 个大群（${orgNames}）中有必填资料尚未完成（临时访问期还剩 ${remainingDays} 天）。请在2周内补齐并获得管理员审核批准，超期将被暂停大群及分队的浏览与活动！`
          : `您在【${firstOrg.name}】中${missingLabels ? "还缺少：" + missingLabels + "。" : "有必填资料尚未完成。"}（临时访问期还剩 ${remainingDays} 天）请在2周内补齐并获得管理员审核批准，超期将被暂停大群及分队的浏览与活动！`;

      return {
        hasReminder: true,
        type: "temporary",
        firstOrg,
        orgCount,
        orgNames,
        missingLabels,
        remainingDays,
        title: "📋 跑者档案待完善",
        content: contentText,
        confirmText: "立即填写",
        cancelText: "稍后再说",
      };
    }
  } catch (e) {
    console.warn("fetchOrgReminderInfo failed:", e);
  }

  return { hasReminder: false, type: "none" };
}

export function navigateToProfileRequiredFields() {
  uni.setStorageSync("auto_scroll_to_required_fields", true);
  uni.switchTab({
    url: "/pages/profile/profile",
  });
}

/** 跳转到【我的】并自动定位到"运动手表数据直连"卡片（支持直接弹出指定品牌重新授权弹窗） */
export function navigateToDeviceBinding(brand?: "garmin" | "coros", autoOpenModal: boolean = false) {
  uni.setStorageSync("auto_scroll_to_device", true);
  if (brand && autoOpenModal) {
    uni.setStorageSync("auto_open_device_brand", brand);
  }
  uni.switchTab({
    url: "/pages/profile/profile",
  });
}

/** 跳转到【跑团】并自动弹出“自建跑团 / 邀请新用户解锁权益”弹窗 */
export function navigateToCreateClub() {
  uni.setStorageSync("team_open_create_club", true);
  uni.switchTab({
    url: "/pages/team/team",
  });
}

export async function checkAndPromptOrgReminder(
  uid: string,
  options: { force?: boolean; preview?: boolean } = {}
): Promise<OrgReminderInfo> {
  let reminder: OrgReminderInfo;
  if (options.preview) {
    reminder = {
      hasReminder: true,
      type: "temporary",
      firstOrg: { name: "复旦戈" },
      missingLabels: "身份证号、紧急联系人及电话、班级/届别",
      remainingDays: 13,
      title: "📋 【复旦戈】档案待完善 (测试预览)",
      content:
        "【测试预览】您在【复旦戈】中尚缺少：身份证号、紧急联系人及电话、班级/届别。（临时访问期还剩 13 天）请在2周内补齐并获得管理员审核批准，超期将被暂停大群及分队的浏览与活动！",
      confirmText: "立即填写",
      cancelText: "稍后再说",
    };
  } else {
    reminder = await fetchOrgReminderInfo(uid);
  }

  if (!reminder.hasReminder) {
    return reminder;
  }

  if (!options.force && !options.preview && _hasPromptedOrgReminderInSession) {
    return reminder;
  }

  _hasPromptedOrgReminderInSession = true;

  uni.showModal({
    title: reminder.title,
    content: reminder.content,
    confirmText: reminder.confirmText || "立即填写",
    cancelText: reminder.cancelText || "稍后再说",
    confirmColor: reminder.type === "suspended" ? "#ef4444" : "#f59e0b",
    success: (res) => {
      if (res.confirm) {
        navigateToProfileRequiredFields();
      }
    },
  });

  return reminder;
}

export interface SupportTicket {
  id: string;
  user_id: string;
  display_name?: string;
  category: string;
  content: string;
  contact_info?: string;
  diagnostic?: Record<string, any>;
  status: "open" | "resolved";
  admin_reply?: string | null;
  replied_at?: string | null;
  created_at: string;
}

export async function submitSupportTicket(payload: {
  uid?: string;
  user_id?: string;
  category: string;
  content: string;
  contact_info?: string;
  device_info?: Record<string, any>;
}) {
  return request("/api/miniapp/support/tickets", "POST", {
    ...payload,
    uid: payload.uid || payload.user_id,
    client_env: "mp-weixin",
  });
}

export async function fetchMySupportTickets(uid: string): Promise<SupportTicket[]> {
  if (!uid) return [];
  const res = await request(`/api/miniapp/support/tickets?uid=${encodeURIComponent(uid)}`);
  return res?.tickets || [];
}

/**
 * 将后端带时区时间戳（如 '...Z'、'...+00:00'、'...+08:00'）统一格式化为北京时间 (UTC+8)
 * 无时区后缀的本地时间字符串保持原样截取。
 */
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


