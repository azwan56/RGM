/**
 * 微信「用户隐私保护指引」授权调度
 *
 * 微信只允许注册一个 wx.onNeedPrivacyAuthorization 监听。这里在 App 启动时注册一次，
 * 触发时按「当前可见页面」分发给该页面上的 <privacy-popup> 组件弹窗。
 * 需要隐私授权的页面（首页 / 我的 / 跑团 / 英雄榜）都挂载了 <privacy-popup>。
 */

export type PrivacyResolve = (res: { event: "agree" | "disagree"; buttonId?: string }) => void;
type PrivacyHandler = (resolve: PrivacyResolve | null) => void;

const handlers = new Map<string, PrivacyHandler>();
let installed = false;

declare const wx: any;

function currentRoute(): string {
  try {
    const pages = getCurrentPages();
    return (pages[pages.length - 1] as any)?.route || "";
  } catch (_) {
    return "";
  }
}

/** App.onLaunch 调用一次 */
export function installPrivacyListener() {
  // #ifdef MP-WEIXIN
  if (installed || typeof wx === "undefined" || typeof wx.onNeedPrivacyAuthorization !== "function") return;
  installed = true;
  wx.onNeedPrivacyAuthorization((resolve: PrivacyResolve) => {
    const handler = handlers.get(currentRoute());
    if (handler) {
      handler(resolve);
      return;
    }
    // 当前页没有挂弹窗：无法在此同意，提示用户回首页完成授权
    resolve({ event: "disagree" });
    uni.showModal({
      title: "需要隐私授权",
      content: "使用该功能前，请先回到首页阅读并同意《用户隐私保护指引》。",
      confirmText: "回首页",
      success: (r) => {
        if (r.confirm) uni.switchTab({ url: "/pages/index/index" });
      },
    });
  });
  // #endif
}

/** 组件挂载时注册（route 为所在页面路径） */
export function registerPrivacyHandler(route: string, handler: PrivacyHandler) {
  if (route) handlers.set(route, handler);
}

export function unregisterPrivacyHandler(route: string, handler: PrivacyHandler) {
  if (route && handlers.get(route) === handler) handlers.delete(route);
}

export function getCurrentRoute() {
  return currentRoute();
}

/** 查询是否仍需授权（用于首次启动主动弹窗） */
export function checkNeedPrivacyAuthorization(): Promise<{ need: boolean; contractName: string }> {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    if (typeof wx !== "undefined" && typeof wx.getPrivacySetting === "function") {
      wx.getPrivacySetting({
        success: (res: any) =>
          resolve({ need: !!res.needAuthorization, contractName: res.privacyContractName || "" }),
        fail: () => resolve({ need: false, contractName: "" }),
      });
      return;
    }
    // #endif
    resolve({ need: false, contractName: "" });
  });
}

export function openPrivacyContract() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== "undefined" && typeof wx.openPrivacyContract === "function") {
    wx.openPrivacyContract({});
  }
  // #endif
}
