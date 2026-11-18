<template>
  <view class="manual-page" :class="themeClass">
    <!-- Compact Hero + Wizard CTA -->
    <view class="rgm-card m3-hero-card">
      <view class="m3-hero-top">
        <view class="m3-hero-meta">
          <text class="m3-hero-title">帮助与使用手册</text>
          <text class="m3-hero-sub">手表绑表 · 跑团实名 · 训练体系问答</text>
        </view>
        <view class="m3-wizard-pill" @click="goToWizard">
          <RgmIcon name="zap" :size="24" color="#ffffff" />
          <text class="m3-wizard-txt">4步向导</text>
        </view>
      </view>

      <!-- Search Bar -->
      <view class="m3-search-box">
        <RgmIcon name="search" :size="26" color="muted" />
        <input
          class="m3-search-input"
          type="text"
          v-model="manualSearch"
          placeholder="搜索问题关键词 (如: 佳明 / 14天 / 退团 / VDOT)..."
        />
        <text v-if="manualSearch" class="m3-search-clear" @click="manualSearch = ''">✕</text>
      </view>

      <!-- 4 Category Filter Tiles -->
      <view class="m3-cat-grid">
        <view
          v-for="cat in manualCategories"
          :key="cat.key"
          class="m3-cat-tile"
          :class="{ active: activeCategory === cat.key }"
          @click="activeCategory = cat.key"
        >
          <RgmIcon :name="cat.icon" :size="28" :color="activeCategory === cat.key ? 'brand' : 'ink'" />
          <text class="m3-cat-lbl">{{ cat.label }}</text>
        </view>
      </view>
    </view>

    <!-- 14-Day Grand Org 3-Step Flow Card -->
    <view v-if="activeCategory === 'all' || activeCategory === 'org'" class="rgm-card m3-flow-card">
      <view class="m3-sec-head">
        <text class="m3-sec-title">大群 14 天实名准入流程</text>
        <text class="m3-warn-pill">超期将冻结大群权限</text>
      </view>
      <view class="m3-flow-steps">
        <view class="m3-step-node">
          <text class="m3-step-idx">1</text>
          <text class="m3-step-lbl">凭码入群</text>
          <text class="m3-step-sub">获得14天临时权</text>
        </view>
        <text class="m3-step-arr">›</text>
        <view class="m3-step-node">
          <text class="m3-step-idx">2</text>
          <text class="m3-step-lbl">补齐 * 必填</text>
          <text class="m3-step-sub">我的 › 隐私设定</text>
        </view>
        <text class="m3-step-arr">›</text>
        <view class="m3-step-node">
          <text class="m3-step-idx">3</text>
          <text class="m3-step-lbl">管理员转正</text>
          <text class="m3-step-sub">长期正式成员</text>
        </view>
      </view>
    </view>

    <!-- Guides List (Filtered by category + search) -->
    <view v-if="filteredGuides.length > 0" class="m3-guide-list">
      <view v-for="g in filteredGuides" :key="g.id" class="rgm-card m3-guide-card">
        <view class="m3-guide-head">
          <text class="m3-guide-badge">{{ g.badge }}</text>
          <text class="m3-guide-title">{{ g.title }}</text>
        </view>
        <view class="m3-guide-items">
          <view v-for="(item, idx) in g.items" :key="idx" class="m3-guide-item">
            <text class="m3-gi-title">{{ item.title }}</text>
            <text class="m3-gi-desc">{{ item.desc }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- Single-Open FAQ Accordion -->
    <view v-if="filteredFaqs.length > 0" class="rgm-card m3-faq-card">
      <view class="m3-sec-head">
        <text class="m3-sec-title">常见问题 FAQ ({{ filteredFaqs.length }})</text>
      </view>
      <view class="m3-faq-list">
        <view
          v-for="faq in filteredFaqs"
          :key="faq.id"
          class="m3-faq-item"
          @click="toggleFaq(faq.id)"
        >
          <view class="m3-faq-qrow">
            <text class="m3-faq-q">{{ faq.q }}</text>
            <RgmIcon :name="expandedFaqId === faq.id ? 'chevron-down' : 'chevron-right'" :size="24" color="muted" />
          </view>
          <text v-if="expandedFaqId === faq.id" class="m3-faq-a">{{ faq.a }}</text>
        </view>
      </view>
    </view>

    <!-- Bottom Support & Share Actions -->
    <view class="rgm-card m3-support-card">
      <view class="m3-support-row">
        <!-- #ifdef MP-WEIXIN -->
        <button class="m3-act-btn is-green" open-type="contact">微信客服</button>
        <!-- #endif -->
        <button class="m3-act-btn is-brand" @click="goToSupport">问题反馈</button>
        <button class="m3-act-btn" @click="goToProfile">个人档案</button>
      </view>
      <!-- #ifdef MP-WEIXIN -->
      <button class="m3-act-btn is-outline" style="margin-top: 14rpx; width: 100%;" open-type="share">
        推荐万跑跑团助手给跑友
      </button>
      <!-- #endif -->
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { currentTheme, themeClass, applySystemTheme } from "../../utils/theme";
import { onShareAppMessage, onShareTimeline, onLoad, onShow } from "@dcloudio/uni-app";
import { initShareMenu, getUnifiedShareAppMessage, getUnifiedShareTimeline } from "../../utils/share";
import RgmIcon from "../../components/RgmIcon.vue";

const manualSearch = ref("");
const activeCategory = ref<"all" | "watch" | "club" | "org" | "privacy">("all");
const expandedFaqId = ref<string>("faq_1");

function toggleFaq(id: string) {
  expandedFaqId.value = expandedFaqId.value === id ? "" : id;
}

const manualCategories: Array<{ key: "all" | "watch" | "club" | "org" | "privacy"; label: string; icon: any }> = [
  { key: "all", label: "全部指引", icon: "compass" },
  { key: "watch", label: "手表绑表", icon: "watch" },
  { key: "club", label: "跑团约跑", icon: "users" },
  { key: "org", label: "大群实名", icon: "shield" },
];

const guidesData = [
  {
    id: "watch_sync",
    category: "watch",
    badge: "手表直连",
    title: "四大主流手表绑定与 PB 导入",
    items: [
      { title: "Garmin (佳明) / COROS (高驰)", desc: "在【我的 → 手表连接】选对应区服（国行佳明选 garmin.cn），绑定后自动同步跑步、HRV、睡眠评分与静息心率。" },
      { title: "Apple Watch / 华为 / 颂拓", desc: "支持截取运动记录详情页批量 OCR 识别导入，或导出 FIT / GPX / TCX 文件在微信聊天中直接导入。" },
      { title: "一键抓取历史 PB", desc: "在【我的 → 训练档案】点“从 Garmin 导入”，自动匹配 5K / 10K / 半马 / 全马最佳成绩。" },
    ],
  },
  {
    id: "club_guide",
    category: "club",
    badge: "跑团约跑",
    title: "自建跑团、约跑与 Canova 排课",
    items: [
      { title: "自建与邀请入团", desc: "支持公开或邀请码准入；跑团成员可查看月度英雄榜、打卡动态、师徒结对及配速列车分队。" },
      { title: "约跑海报与完赛战报", desc: "约跑活动分赛前集结与赛后战报两阶段，支持配速分组选兔（官兔/摄影/补给）及高清海报分享。" },
      { title: "VDOT 与 6 级配速区间", desc: "基于跑力与静息/最大心率自动生成每周周期课表，随每日 HRV 恢复状态动态调优强度。" },
    ],
  },
  {
    id: "org_privacy",
    category: "org",
    badge: "隐私与安全",
    title: "AES-256 实名保护与脱敏控制",
    items: [
      { title: "必填实名信息保护", desc: "姓名、身份证号、手机、紧急联系人与商学院届别均采用银行级 AES-256 加密存储，公开名单自动脱敏为“张*”。" },
      { title: "GPS 路线与生理保密", desc: "在【我的 → 隐私设定】可随时锁定起终点 GPS 轨迹、隐藏心率 HRV，或将 Canova 评语设为仅自己可见，支持一键物理清除隐私。" },
    ],
  },
];

const faqsData = [
  { id: "faq_1", category: "org", q: "为什么提示“大群访问权限已暂停”？", a: "大群有 14 天临时准入期，需在【我的 → 隐私设定】补全标 * 必填字段并经大群管理员审核转正。补齐保存后联系领队转正即可立即恢复。" },
  { id: "faq_2", category: "watch", q: "佳明手表跑步后没有自动同步怎么办？", a: "① 确认 Garmin Connect App 已蓝牙同步完成；② 确认绑定分区（国行选中国区 garmin.cn）；③ 若更改过佳明密码请重新授权绑定一次。" },
  { id: "faq_3", category: "watch", q: "未绑表或苹果/华为用户如何使用？", a: "在首页或【我的 → 手表连接】使用「截图识别导入」或导入 GPX/FIT 轨迹文件，同样参与训练复盘与跑团榜单统计。" },
  { id: "faq_4", category: "privacy", q: "填写真实姓名和身份证安全吗？如何注销？", a: "系统底层采用 AES-256-GCM 密文存储，普通团友不可见明文；【我的 → 隐私设定】底部提供「彻底清除隐私」按钮，可一键物理抹除全部敏感字段与手表授权。" },
  { id: "faq_5", category: "club", q: "退团或被移出跑团会丢失我的历史跑步记录吗？", a: "不会。个人历史跑步记录、手表连接、VDOT 与个人课表 100% 完整保留，仅脱离该跑团排行榜与内部动态。" },
];

const filteredGuides = computed(() => {
  const q = manualSearch.value.trim().toLowerCase();
  return guidesData.filter((g) => {
    if (activeCategory.value !== "all" && g.category !== activeCategory.value) {
      if (!(activeCategory.value === "privacy" && g.id === "org_privacy")) return false;
    }
    if (!q) return true;
    return g.title.toLowerCase().includes(q) || g.items.some((i) => i.title.toLowerCase().includes(q) || i.desc.toLowerCase().includes(q));
  });
});

const filteredFaqs = computed(() => {
  const q = manualSearch.value.trim().toLowerCase();
  return faqsData.filter((f) => {
    if (activeCategory.value !== "all" && f.category !== activeCategory.value) return false;
    if (!q) return true;
    return f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q);
  });
});

onShow(() => {
  applySystemTheme(currentTheme.value);
});

onLoad(() => {
  initShareMenu();
});

onShareAppMessage(() => getUnifiedShareAppMessage());
onShareTimeline(() => getUnifiedShareTimeline());

function goToWizard() {
  uni.navigateTo({ url: "/pages/onboarding/onboarding?step=1" });
}
function goToProfile() {
  uni.setStorageSync("auto_scroll_to_required_fields", true);
  uni.switchTab({ url: "/pages/profile/profile" });
}
function goToSupport() {
  uni.setStorageSync("auto_open_support", true);
  uni.switchTab({ url: "/pages/profile/profile" });
}
</script>

<style scoped>
.manual-page {
  min-height: 100vh;
  background-color: var(--rgm-bg, #0B0B0E);
  padding: 24rpx 28rpx calc(48rpx + constant(safe-area-inset-bottom)) 28rpx;
  padding: 24rpx 28rpx calc(48rpx + env(safe-area-inset-bottom)) 28rpx;
  box-sizing: border-box;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

/* ── Hero Banner ── */
.manual-hero {
  background: var(--rgm-card, linear-gradient(135deg, rgba(252, 76, 2, 0.18) 0%, #151518 100%));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.35));
  border-radius: 24rpx;
  padding: 28rpx 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 16rpx var(--rgm-shadow, rgba(0, 0, 0, 0.22));
  display: flex;
  flex-direction: column;
  gap: 16rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.hero-badge {
  align-self: flex-start;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.2));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.4));
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}

.hero-badge-txt {
  font-size: 22rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #fc4c02);
}

.hero-title {
  font-size: 38rpx;
  font-weight: 900;
  color: var(--rgm-text, #ffffff);
}


.hero-action-row {
  margin-top: 10rpx;
}

.hero-nav-btn {
  background-color: var(--rgm-brand, #fc4c02);
  color: var(--rgm-text, #ffffff);
  font-size: 26rpx;
  font-weight: 700;
  border-radius: 20rpx;
  padding: 16rpx 32rpx;
  display: inline-block;
  border: none;
  box-shadow: 0 4rpx 16rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.3));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* ── Card ── */
.manual-card {
  background-color: var(--rgm-card, #121215);
  border: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.08));
  border-radius: 28rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.org-card-border {
  border-color: rgba(245, 158, 11, 0.35);
  background: var(--rgm-card, linear-gradient(180deg, rgba(245, 158, 11, 0.04) 0%, #121215 100%));
  --rgm-text: var(--rgm-ink); --rgm-text-2: var(--rgm-ink-2); --rgm-text-3: var(--rgm-ink-3);
}

.card-header-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20rpx;
  border-bottom: 1rpx solid var(--rgm-line, rgba(255, 255, 255, 0.06));
  padding-bottom: 20rpx;
  margin-bottom: 24rpx;
}

.step-num-badge {
  width: 56rpx;
  height: 56rpx;
  border-radius: 18rpx;
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.15));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.3));
  color: var(--rgm-brand-text, #fc4c02);
  font-size: 28rpx;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
}

.org-badge-bg {
  background: rgba(245, 158, 11, 0.15);
  border-color: rgba(245, 158, 11, 0.35);
  color: var(--rgm-amber, #fbbf24);
}

.card-header-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-header-title {
  font-size: 30rpx;
  font-weight: 700;
  color: var(--rgm-text, #ffffff);
}


.step-content-box {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.item-block {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.item-title {
  font-size: 26rpx;
  font-weight: 700;
  color: var(--rgm-text, #e4e4e7);
}

.item-desc {
  font-size: 24rpx;
  color: var(--rgm-text-2, #a1a1aa);
  line-height: 1.6;
}

/* ── Tip Boxes ── */
.highlight-tip-box {
  background: var(--rgm-brand-tint, rgba(252, 76, 2, 0.1));
  border: 1rpx solid var(--rgm-brand-line, rgba(252, 76, 2, 0.25));
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.highlight-tip-title {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-brand-text, #ff7a45);
}

.highlight-tip-desc {
  font-size: 22rpx;
  color: var(--rgm-amber, #fed7aa);
  line-height: 1.5;
}

.danger-tip-box {
  background: rgba(239, 68, 68, 0.12);
  border: 1rpx solid rgba(239, 68, 68, 0.3);
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.danger-tip-title {
  font-size: 24rpx;
  font-weight: 700;
  color: var(--rgm-red, #f87171);
}

.danger-tip-desc {
  font-size: 22rpx;
  color: var(--rgm-red, #fca5a5);
  line-height: 1.5;
}

.tip-footer-note {
  background: var(--rgm-tint, rgba(255, 255, 255, 0.03));
  border-radius: 16rpx;
  padding: 16rpx;
  margin-top: 6rpx;
}

.tip-footer-txt {
  font-size: 22rpx;
  color: var(--rgm-text-3, #8e8e93);
  line-height: 1.5;
}

/* ── Bottom Action ── */
.manual-bottom-action {
  padding: 20rpx 0 40rpx;
}

.manual-bottom-btn {
  background: var(--rgm-brand-grad, linear-gradient(135deg, #fc4c02 0%, #ff7a45 100%));
  color: var(--rgm-text, #ffffff);
  font-size: 28rpx;
  font-weight: 700;
  border-radius: 24rpx;
  padding: 24rpx 0;
  border: none;
  box-shadow: 0 8rpx 24rpx var(--rgm-brand-glow, rgba(252, 76, 2, 0.35));
  --rgm-text: var(--rgm-on-brand); --rgm-text-2: var(--rgm-on-brand-2); --rgm-text-3: var(--rgm-on-brand-2);
}

/* C4 Minimalist Help & Manual Styles */
.m3-hero-card { margin-bottom: 18rpx; }
.m3-hero-top {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 18rpx;
}
.m3-hero-meta { display: flex; flex-direction: column; gap: 4rpx; }
.m3-hero-title { font-size: 34rpx; font-weight: 800; color: var(--rgm-ink); }
.m3-hero-sub { font-size: 21rpx; color: var(--rgm-ink-3); }
.m3-wizard-pill {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 8rpx;
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand);
  flex-shrink: 0;
}
.m3-wizard-txt { font-size: 22rpx; font-weight: 700; color: #ffffff; }
.m3-search-box {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12rpx;
  height: 74rpx;
  padding: 0 20rpx;
  border-radius: 18rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line);
  margin-bottom: 16rpx;
}
.m3-search-input { flex: 1; font-size: 24rpx; color: var(--rgm-ink); }
.m3-search-clear { font-size: 24rpx; color: var(--rgm-ink-3); padding: 6rpx; }
.m3-cat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10rpx; }
.m3-cat-tile {
  padding: 14rpx 6rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
}
.m3-cat-tile.active {
  background: var(--rgm-brand-tint);
  border-color: var(--rgm-brand-line);
}
.m3-cat-lbl { font-size: 20rpx; font-weight: 700; color: var(--rgm-ink-2); }
.m3-cat-tile.active .m3-cat-lbl { color: var(--rgm-brand-text); }

.m3-sec-head { display: flex; flex-direction: row; align-items: center; justify-content: space-between; margin-bottom: 16rpx; }
.m3-sec-title { font-size: 27rpx; font-weight: 800; color: var(--rgm-ink); }
.m3-warn-pill {
  font-size: 19rpx;
  font-weight: 700;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-red-tint);
  color: var(--rgm-red);
}
.m3-flow-card { margin-bottom: 18rpx; }
.m3-flow-steps { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 6rpx; }
.m3-step-node {
  flex: 1;
  padding: 14rpx 8rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
}
.m3-step-idx {
  width: 34rpx;
  height: 34rpx;
  line-height: 34rpx;
  text-align: center;
  border-radius: 50%;
  background: var(--rgm-brand);
  color: #ffffff;
  font-size: 20rpx;
  font-weight: 800;
}
.m3-step-lbl { font-size: 22rpx; font-weight: 700; color: var(--rgm-ink); }
.m3-step-sub { font-size: 18rpx; color: var(--rgm-ink-3); text-align: center; }
.m3-step-arr { font-size: 28rpx; color: var(--rgm-ink-3); font-weight: 700; }

.m3-guide-list { display: flex; flex-direction: column; gap: 16rpx; margin-bottom: 18rpx; }
.m3-guide-card { margin-bottom: 0; }
.m3-guide-head { display: flex; flex-direction: row; align-items: center; gap: 12rpx; margin-bottom: 14rpx; }
.m3-guide-badge {
  font-size: 19rpx;
  font-weight: 700;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: var(--rgm-brand-tint);
  color: var(--rgm-brand-text);
  white-space: nowrap;
}
.m3-guide-title { font-size: 26rpx; font-weight: 800; color: var(--rgm-ink); }
.m3-guide-items { display: flex; flex-direction: column; gap: 12rpx; }
.m3-guide-item {
  padding: 14rpx 16rpx;
  border-radius: 16rpx;
  background: var(--rgm-card-2);
  border: 1rpx solid var(--rgm-line);
  display: flex;
  flex-direction: column;
  gap: 4rpx;
}
.m3-gi-title { font-size: 23rpx; font-weight: 700; color: var(--rgm-ink); }
.m3-gi-desc { font-size: 21rpx; color: var(--rgm-ink-2); line-height: 1.5; }

.m3-faq-card { margin-bottom: 18rpx; }
.m3-faq-list { display: flex; flex-direction: column; }
.m3-faq-item {
  padding: 18rpx 0;
  border-bottom: 1rpx solid var(--rgm-line);
}
.m3-faq-item:last-child { border-bottom: none; padding-bottom: 4rpx; }
.m3-faq-qrow { display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 12rpx; }
.m3-faq-q { flex: 1; font-size: 24rpx; font-weight: 700; color: var(--rgm-ink); }
.m3-faq-a { display: block; margin-top: 12rpx; font-size: 22rpx; color: var(--rgm-ink-2); line-height: 1.55; }

.m3-support-card { margin-bottom: 24rpx; }
.m3-support-row { display: flex; flex-direction: row; gap: 12rpx; }
.m3-act-btn {
  flex: 1;
  min-width: 0;
  margin: 0;
  height: 76rpx;
  line-height: 76rpx;
  border-radius: 18rpx;
  font-size: 24rpx;
  font-weight: 700;
  background: var(--rgm-card-2);
  color: var(--rgm-ink);
  border: 1rpx solid var(--rgm-line);
}
.m3-act-btn::after { border: none; }
.m3-act-btn.is-green { background: var(--rgm-green); color: #ffffff; border-color: var(--rgm-green); }
.m3-act-btn.is-brand { background: var(--rgm-brand); color: #ffffff; border-color: var(--rgm-brand); }
.m3-act-btn.is-outline { background: var(--rgm-brand-tint); color: var(--rgm-brand-text); border-color: var(--rgm-brand-line); }
</style>
