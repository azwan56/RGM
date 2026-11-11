<script setup lang="ts">
import { onLaunch, onShow, onHide } from "@dcloudio/uni-app";
import { checkAndAutoLogin, setPendingInviterUid, wechatLogin } from "./utils/api";
import { installPrivacyListener } from "./utils/privacy";
import { initTheme, currentTheme, applySystemTheme } from "./utils/theme";
import { onTelemetryAppLaunch, onTelemetryAppShow, onTelemetryAppHide } from "./utils/telemetry";

function checkMiniProgramUpdate() {
  // #ifdef MP-WEIXIN
  try {
    if (typeof uni !== "undefined" && typeof uni.getUpdateManager === "function") {
      const updateManager = uni.getUpdateManager();
      updateManager.onUpdateReady(() => {
        uni.showModal({
          title: "发现新版本",
          content: "新版本已准备就绪，请点击确定重启小程序以应用最新界面与功能。",
          showCancel: false,
          confirmText: "立即重启",
          success: (res) => {
            if (res.confirm) {
              updateManager.applyUpdate();
            }
          },
        });
      });
    }
  } catch (e) {
    console.warn("UpdateManager check failed:", e);
  }
  // #endif
}

declare function getCurrentPages(): any[];

function routeWebQrSceneIfNeeded(options?: any) {
  try {
    const rawScene = decodeURIComponent(String(options?.query?.scene || "")).trim();
    if (!rawScene.startsWith("wlogin_")) return;
    const lastRouted = (uni as any).__lastWebQrScene || "";
    if (lastRouted === rawScene) return;
    (uni as any).__lastWebQrScene = rawScene;

    const curPath = String(options?.path || "").replace(/^\/+/, "");
    if (curPath !== "pages/share/share") {
      setTimeout(() => {
        uni.navigateTo({
          url: `/pages/share/share?scene=${encodeURIComponent(rawScene)}`,
        });
      }, 150);
    } else {
      const pages = typeof getCurrentPages === "function" ? getCurrentPages() : [];
      const top: any = pages && pages.length > 0 ? pages[pages.length - 1] : null;
      const topRoute = String(top?.route || top?.$page?.route || "").replace(/^\/+/, "");
      const topScene = decodeURIComponent(String(top?.options?.scene || "")).trim();
      if (topRoute === "pages/share/share" && topScene && topScene !== rawScene) {
        uni.redirectTo({
          url: `/pages/share/share?scene=${encodeURIComponent(rawScene)}`,
        });
      }
    }
  } catch (_) {}
}

onLaunch((options?: any) => {
  console.log("RGM MiniApp Launched", options);
  onTelemetryAppLaunch(options);
  initTheme();
  checkMiniProgramUpdate();
  // 微信隐私保护指引：全局只注册一次，按当前页面分发到 <PrivacyPopup>
  installPrivacyListener();
  routeWebQrSceneIfNeeded(options);
  const inviterUid = options?.query?.inviter_uid;
  if (inviterUid) {
    setPendingInviterUid(inviterUid);
  }
  const existingUser = checkAndAutoLogin();
  if (!existingUser && inviterUid) {
    wechatLogin();
  }
});

onShow((options?: any) => {
  console.log("App Show");
  onTelemetryAppShow(options);
  applySystemTheme(currentTheme.value);
  checkMiniProgramUpdate();
  routeWebQrSceneIfNeeded(options);
  const inviterUid = options?.query?.inviter_uid;
  if (inviterUid) {
    setPendingInviterUid(inviterUid);
    if (!checkAndAutoLogin()) {
      wechatLogin();
    }
  }
});

onHide(() => {
  console.log("App Hide");
  onTelemetryAppHide();
});
</script>

<style>
@import "./styles/theme.css";

/* Global Design System Aesthetic */
page {
  background-color: var(--rgm-bg, #0B0B0E);
  color: var(--rgm-text, #F4F4F6);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  font-variant-numeric: tabular-nums;
  box-sizing: border-box;
  -webkit-font-smoothing: antialiased;
}

view, text, button, input, image {
  box-sizing: border-box;
}

/* 跨平台（iOS / Android）原生 button 统一居中与防截断重置 */
button {
  margin-left: 0;
  margin-right: 0;
  padding-left: 16rpx;
  padding-right: 16rpx;
  line-height: 1.25;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  box-sizing: border-box;
}

button::after {
  border: none;
}

/* Scrollbar hidden */
::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
  color: transparent;
}

/* 空状态统一行动按钮：每个空状态都应给出一个"下一步"入口 */
.rgm-empty-cta {
  display: flex;
  width: fit-content;
  align-items: center;
  justify-content: center;
  margin: 24rpx auto 0;
  padding: 0 40rpx;
  height: 72rpx;
  line-height: 1.25;
  white-space: nowrap;
  border-radius: 36rpx;
  background-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: 600;
  border: none;
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}
.rgm-empty-cta::after {
  border: none;
}
.rgm-empty-cta.ghost {
  background-color: var(--rgm-brand-tint, rgba(252, 76, 2, 0.12));
  color: var(--rgm-brand-text, #fc4c02);
  border: 1px solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
}

/* 术语解释 ⓘ：点击弹出白话说明（utils/glossary.ts） */
.term-info {
  display: inline-block;
  margin-left: 8rpx;
  padding: 0 6rpx;
  font-size: 24rpx;
  color: var(--rgm-text-3, #71717a);
  font-weight: 400;
}
</style>
