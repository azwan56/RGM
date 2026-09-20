<template>
  <view class="manual-page">
    <!-- Header Banner -->
    <view class="manual-hero">
      <view class="hero-badge">
        <text class="hero-badge-txt">📖 官方新用户手册</text>
      </view>
      <text class="hero-title">跑者快速上手与指引</text>
      <text class="hero-desc">
        3 分钟快速完成账号登录、手表数据直连、复旦戈大群体实名认证与训练目标规划。
      </text>

      <view class="hero-action-row">
        <button class="hero-nav-btn" @click="goToProfile">
          前往完善个人档案 ›
        </button>
      </view>
    </view>

    <!-- ── 1. 账号注册与一键登录 ── -->
    <view class="manual-card">
      <view class="card-header-row">
        <view class="step-num-badge">1</view>
        <view class="card-header-meta">
          <text class="card-header-title">账号注册与一键登录</text>
          <text class="card-header-sub">微信小程序与 Web 网页端全量打通</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="item-block">
          <text class="item-title">📱 微信小程序端（日常打卡与交流首选）：</text>
          <text class="item-desc">
            1. 微信搜索「万跑跑团助手」或长按识别跑团码、活动分享海报。
          </text>
          <text class="item-desc">
            2. 点击底部导航栏【我的】。
          </text>
          <text class="item-desc">
            3. 点击顶部醒目的【🟢 微信一键快速登录】按钮完成授权。
          </text>
          <text class="item-desc">
            4. 登录后点击跑者卡片可随时修改昵称或上传个性化头像。
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">💻 Web 网页管理端（大屏看板与深度分析）：</text>
          <text class="item-desc">
            在电脑浏览器访问 rgm.vanpower.net，支持点击微信扫码秒级登录，数据与小程序实时互通。
          </text>
        </view>
      </view>
    </view>

    <!-- ── 2. 绑定手表与导入运动历史 ── -->
    <view class="manual-card">
      <view class="card-header-row">
        <view class="step-num-badge">2</view>
        <view class="card-header-meta">
          <text class="card-header-title">绑定运动手表与导入历史</text>
          <text class="card-header-sub">Garmin 佳明 & COROS 高驰官方直连</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="item-block">
          <text class="item-title">⌚ Garmin (佳明) 手表直连：</text>
          <text class="item-desc">
            在【我的】→【个人资料与账号】找到“运动手表直连”，点击【绑定佳明账号】。
          </text>
          <text class="item-desc">
            • 国行设备务必选择“中国区 (garmin.cn)”；海外账号选“国际区”。
          </text>
          <text class="item-desc">
            • 输入 Garmin Connect App 账号密码，系统将开启后台静默自动同步，跑步后 1~3 分钟自动出报告。
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">⚡ COROS (高驰) 手表直连：</text>
          <text class="item-desc">
            点击【绑定高驰账号】，输入 COROS App 绑定的手机/邮箱及密码完成授权。
          </text>
        </view>

        <view class="highlight-tip-box">
          <text class="highlight-tip-title">⚡ 一键导入历史个人最好成绩 (PB)：</text>
          <text class="highlight-tip-desc">
            绑定佳明后，切换至【训练档案与赛事】标签页，点击“个人最佳成绩 (PB)”右上角的【从 Garmin 一键导入】，系统将自动抓取 5K/10K/半马/全马最快记录！
          </text>
        </view>
      </view>
    </view>

    <!-- ── 3. 加入复旦戈大群与资料规范 ── -->
    <view class="manual-card org-card-border">
      <view class="card-header-row">
        <view class="step-num-badge org-badge-bg">3</view>
        <view class="card-header-meta">
          <text class="card-header-title">加入“复旦戈”大群与实名资料规范</text>
          <text class="card-header-sub">严格实行“2周实名核验准入制”</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="danger-tip-box">
          <text class="danger-tip-title">⚠️ 2周准入限期铁律（必读）：</text>
          <text class="danger-tip-desc">
            新加入“复旦戈”后进入 14 天临时访问期。队员必须在 14 天内填齐所有标有红星 * 的必填资料，并由管理员后台审核转正。超期未完成将被系统自动暂停访问该大群及所有从属跑团（如复旦戈闵文跑团）的一切看板、动态、打卡与活动！
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">📋 必填字段清单与填写指引：</text>
          <text class="item-desc">
            • 真实姓名 *：实名认证姓名，底层采用 AES-256 加密存储，公开名册自动以“张*”脱敏保护。
          </text>
          <text class="item-desc">
            • 生理性别 *：男 / 女，用于戈赛男女名额配比与科学训练区间计算。
          </text>
          <text class="item-desc">
            • 出生日期 *：点击选择出生年月日，自动推算实岁与青年/壮年/大师组别（公开名册绝不暴露具体生日）。
          </text>
          <text class="item-desc">
            • 商学院项目 *：下拉选择中文EMBA、台大班、复旦-BI、奥林班、港大班等。
          </text>
          <text class="item-desc">
            • 所在班级/届别 *：填写所在班级或期数（如：2022春2班、38期）。
          </text>
          <text class="item-desc">
            • 戈壁经历：选择新戈或老戈（老戈选戈几及 A/B/C 组）。
          </text>
          <text class="item-desc">
            • 联系手机与身份证号：用于越野拉练与团队比赛统一购买意外保险，高强度保密存储。
          </text>
        </view>

        <view class="tip-footer-note">
          <text class="tip-footer-txt">
            填毕后务必点击底部的【💾 保存个人资料与账号设置】。若超期被暂停，补齐保存后联系大群管理员（或领队）点击【确认转正】即可即刻解冻恢复！
          </text>
        </view>
      </view>
    </view>

    <!-- ── 4. 生理指标与配速测算 ── -->
    <view class="manual-card">
      <view class="card-header-row">
        <view class="step-num-badge">4</view>
        <view class="card-header-meta">
          <text class="card-header-title">生理指标与 Canova 配速体系</text>
          <text class="card-header-sub">智能测算 VO2Max 与 6 级个性化配速区间</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="item-block">
          <text class="item-title">💓 核心指标设定（在【训练档案与赛事】标签中）：</text>
          <text class="item-desc">
            1. 最大摄氧量 (VO2Max)：点击【⚡ 依据 PB 测算】，基于丹尼尔斯 VDOT 算法自动推算；亦可点击【从手表同步指标】抓取手表测算值。
          </text>
          <text class="item-desc">
            2. 静息心率与最大心率：设定清晨静息心率与极限心率，用于精准预警过度疲劳与心脏负荷。
          </text>
          <text class="item-desc">
            3. 身高体重与跑龄：Canova AI 教练将据此自适应生成 6 级配速区间与超量恢复时间窗口。
          </text>
        </view>
      </view>
    </view>

    <!-- ── 5. 设立周/月/比赛目标 ── -->
    <view class="manual-card">
      <view class="card-header-row">
        <view class="step-num-badge">5</view>
        <view class="card-header-meta">
          <text class="card-header-title">设立训练目标与周/月计划</text>
          <text class="card-header-sub">跑量规划 · 本周重点目标卡 · 赛事倒计时</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="item-block">
          <text class="item-title">📅 2026 年度与月跑量规划：</text>
          <text class="item-desc">
            • 全年统一均值：拖动滑块直接设定每月跑量（如 200 km/月）。
          </text>
          <text class="item-desc">
            • 按月自定义：在 1~12 月网格中输入不同月份进阶跑量（如夏训 160km → 选拔拉练 260km），系统自动汇总全年目标。
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">🎯 本周重点跑量目标卡：</text>
          <text class="item-desc">
            点击快捷胶囊（30km、40km、50km、60km、70km+）设定本周挑战，点击【单独保存周跑量目标】生效。首页将实时展示周进度环形图与剩余里程。
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">🏁 比赛计划与 AI 赛事情报：</text>
          <text class="item-desc">
            点击【添加比赛计划】输入赛事名称与日期（支持倒计时提醒、AI 赛道起伏检索与完赛照片战报生成）。
          </text>
        </view>
      </view>
    </view>

    <!-- ── 6. 常见问答 FAQ ── -->
    <view class="manual-card">
      <view class="card-header-row">
        <view class="step-num-badge">?</view>
        <view class="card-header-meta">
          <text class="card-header-title">常见问答与排错 (FAQ)</text>
          <text class="card-header-sub">高频问题一键自查解答</text>
        </view>
      </view>

      <view class="step-content-box">
        <view class="item-block">
          <text class="item-title">Q1: 为什么提示“跑团访问权限已暂停”？</text>
          <text class="item-desc">
            解答：这说明您所在跑团隶属于“复旦戈”大群，而您的大群 14 天临时准入期已过，但实名资料中有 * 必填项未补齐，或管理员尚未审核。请进入【我的】补齐并保存，联系领队或大群管理员转正后即可解冻！
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">Q2: 佳明手表跑步后没有同步过来怎么办？</text>
          <text class="item-desc">
            解答：① 确认 Garmin Connect 手机 App 已完成蓝牙同步；② 确认绑定时分区是否选对（国行选中国区）；③ 若修改了佳明密码，请重新绑定一次。
          </text>
        </view>

        <view class="item-block">
          <text class="item-title">Q3: 填写真实姓名和身份证安全吗？</text>
          <text class="item-desc">
            解答：绝对安全。系统底层严格采用银行级 AES-256-GCM 高强度密文存储，公开名册仅显示脱敏星号姓名（如：张*）与年龄组别，普通跑友无法查看明文，且您随时可一键彻底清除隐私底账。
          </text>
        </view>
      </view>
    </view>

    <!-- Bottom Action Button -->
    <view class="manual-bottom-action">
      <button class="manual-bottom-btn" @click="goToProfile">
        立即前往完善个人档案与设置
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
function goToProfile() {
  uni.switchTab({
    url: "/pages/profile/profile",
  });
}
</script>

<style scoped>
.manual-page {
  min-height: 100vh;
  background-color: #0b0b0d;
  padding: 24rpx 24rpx 80rpx;
  box-sizing: border-box;
}

/* ── Hero Banner ── */
.manual-hero {
  background: linear-gradient(135deg, rgba(252, 76, 2, 0.18) 0%, #151518 100%);
  border: 1rpx solid rgba(252, 76, 2, 0.35);
  border-radius: 32rpx;
  padding: 36rpx 32rpx;
  margin-bottom: 28rpx;
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.hero-badge {
  align-self: flex-start;
  background: rgba(252, 76, 2, 0.2);
  border: 1rpx solid rgba(252, 76, 2, 0.4);
  padding: 6rpx 16rpx;
  border-radius: 20rpx;
}

.hero-badge-txt {
  font-size: 22rpx;
  font-weight: 700;
  color: #fc4c02;
}

.hero-title {
  font-size: 38rpx;
  font-weight: 900;
  color: #ffffff;
}

.hero-desc {
  font-size: 24rpx;
  color: #a0a0a5;
  line-height: 1.6;
}

.hero-action-row {
  margin-top: 10rpx;
}

.hero-nav-btn {
  background-color: #fc4c02;
  color: #ffffff;
  font-size: 26rpx;
  font-weight: 700;
  border-radius: 20rpx;
  padding: 16rpx 32rpx;
  display: inline-block;
  border: none;
  box-shadow: 0 4rpx 16rpx rgba(252, 76, 2, 0.3);
}

/* ── Card ── */
.manual-card {
  background-color: #121215;
  border: 1rpx solid rgba(255, 255, 255, 0.08);
  border-radius: 28rpx;
  padding: 32rpx;
  margin-bottom: 24rpx;
}

.org-card-border {
  border-color: rgba(245, 158, 11, 0.35);
  background: linear-gradient(180deg, rgba(245, 158, 11, 0.04) 0%, #121215 100%);
}

.card-header-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 20rpx;
  border-bottom: 1rpx solid rgba(255, 255, 255, 0.06);
  padding-bottom: 20rpx;
  margin-bottom: 24rpx;
}

.step-num-badge {
  width: 56rpx;
  height: 56rpx;
  border-radius: 18rpx;
  background: rgba(252, 76, 2, 0.15);
  border: 1rpx solid rgba(252, 76, 2, 0.3);
  color: #fc4c02;
  font-size: 28rpx;
  font-weight: 900;
  display: flex;
  align-items: center;
  justify-content: center;
}

.org-badge-bg {
  background: rgba(245, 158, 11, 0.15);
  border-color: rgba(245, 158, 11, 0.35);
  color: #fbbf24;
}

.card-header-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.card-header-title {
  font-size: 30rpx;
  font-weight: 700;
  color: #ffffff;
}

.card-header-sub {
  font-size: 22rpx;
  color: #8e8e93;
  margin-top: 4rpx;
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
  color: #e4e4e7;
}

.item-desc {
  font-size: 24rpx;
  color: #a1a1aa;
  line-height: 1.6;
}

/* ── Tip Boxes ── */
.highlight-tip-box {
  background: rgba(252, 76, 2, 0.1);
  border: 1rpx solid rgba(252, 76, 2, 0.25);
  border-radius: 20rpx;
  padding: 20rpx;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.highlight-tip-title {
  font-size: 24rpx;
  font-weight: 700;
  color: #ff7a45;
}

.highlight-tip-desc {
  font-size: 22rpx;
  color: #fed7aa;
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
  color: #f87171;
}

.danger-tip-desc {
  font-size: 22rpx;
  color: #fca5a5;
  line-height: 1.5;
}

.tip-footer-note {
  background: rgba(255, 255, 255, 0.03);
  border-radius: 16rpx;
  padding: 16rpx;
  margin-top: 6rpx;
}

.tip-footer-txt {
  font-size: 22rpx;
  color: #8e8e93;
  line-height: 1.5;
}

/* ── Bottom Action ── */
.manual-bottom-action {
  padding: 20rpx 0 40rpx;
}

.manual-bottom-btn {
  background: linear-gradient(135deg, #fc4c02 0%, #ff7a45 100%);
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
  border-radius: 24rpx;
  padding: 24rpx 0;
  border: none;
  box-shadow: 0 8rpx 24rpx rgba(252, 76, 2, 0.35);
}
</style>
