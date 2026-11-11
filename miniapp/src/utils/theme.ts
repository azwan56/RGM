import { ref, computed } from "vue";

export type ThemeMode = "dark" | "volt";
export type FontScaleMode = "normal" | "large" | "xlarge";

const THEME_STORAGE_KEY = "rgm_theme";
const FONT_SCALE_STORAGE_KEY = "rgm_font_scale";

export const FONT_SCALE_OPTIONS: Array<{ key: FontScaleMode; label: string; scale: number }> = [
  { key: "normal", label: "标准", scale: 1 },
  { key: "large", label: "大字", scale: 1.12 },
  { key: "xlarge", label: "特大", scale: 1.22 },
];

// 全局响应式主题状态：仅保留 'dark' (🌑 经典暗黑) 与 'volt' (⚡ 经典竞技) 两套主题
export const currentTheme = ref<ThemeMode>("dark");
// 全局响应式字号档位：'normal' (1.0x) | 'large' (1.12x) | 'xlarge' (1.22x)
export const currentFontScale = ref<FontScaleMode>("normal");

export const isVolt = computed(() => currentTheme.value === "volt");
export const isTrail = computed(() => false);
export const isDark = computed(() => currentTheme.value === "dark");

export const fontScaleClass = computed(() => {
  if (currentFontScale.value === "large") return "font-large";
  if (currentFontScale.value === "xlarge") return "font-xlarge";
  return "";
});

export const themeClass = computed(() => {
  const base = currentTheme.value === "volt" ? "theme-volt" : "theme-dark";
  return fontScaleClass.value ? `${base} ${fontScaleClass.value}` : base;
});

function detectDefaultFontScale(): FontScaleMode {
  try {
    const info = (uni as any).getAppBaseInfo?.();
    const sysPx = Number(info?.fontSizeSetting || 0);
    if (sysPx >= 22) return "xlarge";
    if (sysPx >= 19) return "large";
  } catch (_) {}
  return "normal";
}

/**
 * 初始化主题与字号：从本地缓存读取用户偏好，若未设定字号则自动参考微信系统字号
 * 兼容旧版 'trail' 缓存自动迁移为 'volt'
 */
export function initTheme(): ThemeMode {
  try {
    const saved = uni.getStorageSync(THEME_STORAGE_KEY) as string;
    if (saved === "volt" || saved === "trail") {
      currentTheme.value = "volt";
      if (saved === "trail") {
        uni.setStorageSync(THEME_STORAGE_KEY, "volt");
      }
    } else {
      currentTheme.value = "dark";
    }
  } catch (e) {
    currentTheme.value = "dark";
  }

  try {
    const savedScale = uni.getStorageSync(FONT_SCALE_STORAGE_KEY) as string;
    if (savedScale === "normal" || savedScale === "large" || savedScale === "xlarge") {
      currentFontScale.value = savedScale;
    } else {
      currentFontScale.value = detectDefaultFontScale();
    }
  } catch (_) {
    currentFontScale.value = "normal";
  }

  applySystemTheme(currentTheme.value);
  return currentTheme.value;
}

/**
 * 切换并持久化全局字号档位
 */
export function setFontScale(mode: FontScaleMode) {
  const normalized: FontScaleMode =
    mode === "large" || mode === "xlarge" ? mode : "normal";
  currentFontScale.value = normalized;
  try {
    uni.setStorageSync(FONT_SCALE_STORAGE_KEY, normalized);
  } catch (e) {
    console.warn("Failed to save font scale preference:", e);
  }
  try {
    if (typeof uni !== "undefined" && typeof uni.vibrateShort === "function") {
      uni.vibrateShort({ type: "light" } as any);
    }
  } catch (_) {}
  syncTabBarTheme();
}

/**
 * 切换并持久化主题
 */
export function setTheme(mode: ThemeMode) {
  const normalized: ThemeMode = mode === "volt" ? "volt" : "dark";
  currentTheme.value = normalized;
  try {
    uni.setStorageSync(THEME_STORAGE_KEY, normalized);
  } catch (e) {
    console.warn("Failed to save theme preference:", e);
  }
  applySystemTheme(normalized);
  syncTabBarTheme(normalized);
}

/**
 * 一键在「🌑 经典暗黑」与「⚡ 经典竞技」之间切换（对齐 iOS 顶部胶囊交互）
 */
export function toggleTheme(): ThemeMode {
  const next: ThemeMode = currentTheme.value === "volt" ? "dark" : "volt";
  setTheme(next);
  try {
    if (typeof uni !== "undefined" && typeof uni.vibrateShort === "function") {
      uni.vibrateShort({ type: "light" } as any);
    }
  } catch (_) {}
  return next;
}

/**
 * 应用原生导航栏与页面底色，保证系统级体验一致
 */
export function applySystemTheme(mode: ThemeMode) {
  if (mode === "volt") {
    // ☀️ 竞技亮色 v3.0 (60% 纯白/雾灰 × 30% 深海蓝黑 × 10% 万跑品牌橙 #FC4C02)
    uni.setNavigationBarColor({
      frontColor: "#000000",
      backgroundColor: "#ffffff",
      animation: { duration: 150, timingFunc: "easeInOut" }
    }).catch(() => {});
    uni.setBackgroundColor({
      backgroundColor: "#F6F8FA",
      backgroundColorTop: "#ffffff",
      backgroundColorBottom: "#F6F8FA"
    }).catch(() => {});
  } else {
    // 🌑 经典暗黑 (Dark Classic)
    uni.setNavigationBarColor({
      frontColor: "#ffffff",
      backgroundColor: "#0B0B0E",
      animation: { duration: 150, timingFunc: "easeInOut" }
    }).catch(() => {});
    uni.setBackgroundColor({
      backgroundColor: "#0B0B0E",
      backgroundColorTop: "#0B0B0E",
      backgroundColorBottom: "#0B0B0E"
    }).catch(() => {});
  }
}

/**
 * 触发自定义 TabBar 同步主题色与图标
 */
export function syncTabBarTheme(mode?: ThemeMode) {
  const m: ThemeMode = (mode || currentTheme.value) === "volt" ? "volt" : "dark";
  try {
    // #ifdef MP-WEIXIN
    const pages = getCurrentPages();
    if (pages && pages.length) {
      const cur = pages[pages.length - 1];
      if (cur && typeof (cur as any).getTabBar === "function") {
        const tb = (cur as any).getTabBar();
        if (tb) {
          if (typeof tb.syncTheme === "function") {
            tb.syncTheme();
          } else if (typeof tb.setData === "function") {
            tb.setData({ theme: m, fontScale: currentFontScale.value });
          }
        }
      }
    }
    // #endif
  } catch (e) {
    // ignore
  }
}

/**
 * 图表 / SVG / Canvas 配色（Canvas 无法读取 CSS 变量，需在 JS 里按主题取色）。
 */
export const chartPalette = computed(() => {
  const mode = currentTheme.value;
  if (mode === "dark") {
    return {
      grid: "#202026", gridZero: "#383842", axis: "#71717a", axisStrong: "#9ca3af",
      cross: "rgba(255, 255, 255, 0.35)", svgGrid: "rgba(255,255,255,0.08)",
      brand: "#FC4C02", brandText: "#fb923c",
      ctl: "#38bdf8", atl: "#ec4899", hrv: "#06b6d4", rhr: "#ef4444", sleep: "#818cf8", battery: "#eab308"
    };
  }
  return {
    grid: "#E2E8F0", gridZero: "#CBD5E1", axis: "#475569", axisStrong: "#0F172A",
    cross: "rgba(15, 23, 42, 0.40)", svgGrid: "rgba(15,23,42,0.08)",
    brand: "#FC4C02", brandText: "#C23800",
    ctl: "#0284C7", atl: "#E11D48", hrv: "#0891B2", rhr: "#DC2626", sleep: "#4F46E5", battery: "#EA580C"
  };
});
