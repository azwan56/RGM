"use client";

import { useState } from "react";
import Link from "next/link";

type Lang = "zh" | "en";

export default function PrivacyPolicy() {
  const [lang, setLang] = useState<Lang>("zh");

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-100 flex flex-col relative font-sans">
      {/* Background aesthetic blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-[#FC4C02]/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/5 blur-[150px] pointer-events-none" />

      {/* Main Container */}
      <main className="max-w-4xl mx-auto px-4 md:px-8 pt-24 pb-16 relative z-10 flex-1 w-full">
        {/* Header Navigation */}
        <div className="flex items-center justify-between mb-8 pb-6 border-b border-white/10">
          <Link
            href="/"
            className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors group"
          >
            <svg className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            {lang === "zh" ? "返回首页" : "Back to Home"}
          </Link>

          {/* Language Switcher */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-0.5 flex gap-1">
            <button
              onClick={() => setLang("zh")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                lang === "zh"
                  ? "bg-[#FC4C02] text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              中文
            </button>
            <button
              onClick={() => setLang("en")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                lang === "en"
                  ? "bg-[#FC4C02] text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              English
            </button>
          </div>
        </div>

        {/* Content Block */}
        <article className="prose prose-invert max-w-none space-y-6">
          {lang === "zh" ? (
            // ── CHINESE VERSION ──────────────────────────────────────────────
            <>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-2">
                隐私政策及个人数据声明
              </h1>
              <p className="text-xs text-zinc-500">最近更新日期：2026年7月14日</p>
              
              <p className="text-zinc-300 leading-relaxed mt-4">
                欢迎使用 <strong>RGM (跑团管理平台)</strong>。我们非常重视您的个人隐私和数据安全。本《隐私政策》详细阐述了我们在您使用平台期间如何收集、使用、存储和保护您的数据。
              </p>

              <hr className="border-white/10 my-6" />

              <h2 className="text-xl font-bold text-white mt-8">1. 我们收集的信息</h2>
              <p className="text-zinc-300">为了实现跑团管理、活动分析和排行榜功能，我们需要收集以下几类数据：</p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>
                  <strong>注册基本信息</strong>：您在注册时提供的邮箱地址、密码、头像、自定义显示昵称（Display Name）以及身高、体重、跑龄等基础生理参数。
                </li>
                <li>
                  <strong>Strava 运动数据</strong>：通过授权 Strava，我们会拉取您的运动历史记录，包括运动 ID、距离、耗时、配速、GPS 轨迹（Polyline）、海拔起伏、平均与最大心率、步频（Cadence）以及您绑定的跑鞋设备（Gear ID）等。
                </li>
                <li>
                  <strong>外部健康数据 (当您启用时)</strong>：如您未来授权连接 Google Health，我们将拉取您的日常静息心率 (RHR)、心率变异性 (HRV) 和睡眠得分与时长等训练外的恢复数据，以便更综合地评估您的体能与疲劳状态。
                </li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">2. 我们如何使用您的信息</h2>
              <p className="text-zinc-300">我们收集的数据仅用于为您和您所在的跑团提供核心分析及社交互动，具体包括：</p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>计算您的体育科学指标，包括 TRIMP (训练冲量)、CTL (体能)、ATL (疲劳)、TSB (状态值) 和 VDOT (跑力值) 等。</li>
                <li>用于生成团队内的月度/周度跑量排行榜（Leaderboard）以及团队数据统计。</li>
                <li>通过 AI 教练（基于 Renato Canova 的训练哲学）为您提供个性化的备赛建议和恢复指南。</li>
                <li>在您配置了 Discord 或企业微信 Webhook 时，自动为您推送周报和新跑步记录通知。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">3. 数据共享与披露</h2>
              <p className="text-zinc-300"><strong>我们坚守以下数据隐私底线：</strong></p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li><strong>绝不转售</strong>：我们绝对不会向任何广告商、第三方营销机构转售您的任何数据。</li>
                <li><strong>绝不用作 AI 训练</strong>：您的数据仅供本平台的规则算法和 AI 教练上下文推理使用，绝对不会用于训练任何通用的公共人工智能大模型。</li>
                <li><strong>团队公开范围</strong>：只有您的跑量、平均配速、平均心率、目标完成率和头像会在您主动加入的跑团队伍排行榜中展示，其他成员无法查看您的底层 GPS 轨迹或详细健康日志（如睡眠详情）。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">4. 数据存储与安全</h2>
              <p className="text-zinc-300">
                我们的平台数据托管于 **Google Cloud Platform (GCP)** 的 Firestore 数据库中。我们会采取符合行业标准的加密与安全防护措施，防止您的数据发生丢失、滥用或未经授权的访问。
              </p>

              <h2 className="text-xl font-bold text-white mt-8">5. 您的权利与选择</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>您可以随时在 RGM 个人档案页面更改您的生理参数、目标或头像。</li>
                <li>您可以随时解除与 Strava 或 Google Health 的授权，届时本平台将不再自动同步新的数据。</li>
                <li>如果您需要彻底删除在 RGM 平台上的账号及所有同步历史，请联系平台管理员，我们将在收到请求后 7 个工作日内彻底清空您在 Firestore 中的所有关联文档。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">6. 政策更新</h2>
              <p className="text-zinc-300">
                我们可能会因平台功能升级或法律合规要求适时更新本隐私政策。更新后我们会在登录界面或以平台通知的形式告知您。
              </p>

              <h2 className="text-xl font-bold text-white mt-8">7. 联系我们</h2>
              <p className="text-zinc-300">
                如果您对本隐私政策有任何疑问，或需要请求删除数据，请发送邮件至平台管理邮箱。
              </p>
            </>
          ) : (
            // ── ENGLISH VERSION ──────────────────────────────────────────────
            <>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-2">
                Privacy Policy & Personal Data Declaration
              </h1>
              <p className="text-xs text-zinc-500">Last Updated: July 14, 2026</p>

              <p className="text-zinc-300 leading-relaxed mt-4">
                Welcome to <strong>RGM (Running Community Manager)</strong>. We are deeply committed to protecting your personal privacy and the security of your data. This Privacy Policy details how we collect, use, store, and protect your information while using our platform.
              </p>

              <hr className="border-white/10 my-6" />

              <h2 className="text-xl font-bold text-white mt-8">1. Information We Collect</h2>
              <p className="text-zinc-300">To provide running community management, activity analysis, and leaderboard features, we collect the following types of data:</p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>
                  <strong>Basic Account Information</strong>: Email address, password, avatar, customized display name, and physiological parameters such as height, weight, running age, and gender provided during registration.
                </li>
                <li>
                  <strong>Strava Activity Data</strong>: By authorizing Strava, we retrieve your workout history, including activity IDs, distance, moving/elapsed time, pace, GPS routes (Polylines), elevation gain, average/maximum heart rate, cadence, and attached shoe/gear details (Gear ID).
                </li>
                <li>
                  <strong>External Health Data (Optional)</strong>: If you choose to authorize Google Health/Health Connect in the future, we will collect off-training recovery metrics such as daily Resting Heart Rate (RHR), Heart Rate Variability (HRV), and sleep scores/durations to provide a more holistic fatigue and readiness assessment.
                </li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">2. How We Use Your Information</h2>
              <p className="text-zinc-300">The collected data is exclusively used to deliver sports science analysis and running group interactions, including:</p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>Calculating sports science metrics such as TRIMP (Training Impulse), CTL (Fitness), ATL (Fatigue), TSB (Form/Readiness), and VDOT (Running Fitness).</li>
                <li>Generating monthly/weekly running distance leaderboards and aggregate team statistics.</li>
                <li>Providing personalized race preparation guidance and recovery tips via the AI Coach (fueled by Renato Canova’s training philosophy).</li>
                <li>Delivering weekly reports and new activity notifications if you configure Discord or WeCom Webhooks.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">3. Data Sharing and Disclosure</h2>
              <p className="text-zinc-300"><strong>We strictly adhere to the following privacy boundaries:</strong></p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li><strong>No Reselling</strong>: We will never sell your personal data to any advertisers or third-party marketing firms.</li>
                <li><strong>No AI Model Training</strong>: Your data is only used for rule-based computations and AI Coach context retrieval. It will never be used to train generic, public large language models.</li>
                <li><strong>Visibility Controls</strong>: Only your distance, average pace, average heart rate, goal completion percentage, and avatar are displayed on the leaderboards of the teams you actively join. Detailed GPS routes and granular health logs (such as sleep breakdowns) remain strictly private to you.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">4. Data Storage and Security</h2>
              <p className="text-zinc-300">
                Our application data is securely hosted on **Google Cloud Platform (GCP)** in Firestore databases. We adopt industry-standard encryption and security measures to protect against loss, misuse, or unauthorized access.
              </p>

              <h2 className="text-xl font-bold text-white mt-8">5. Your Rights and Choices</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>You can update your physical parameters, goals, or avatar in your RGM Profile at any time.</li>
                <li>You can revoke Strava or Google Health integration at any time, which will stop automatic syncs.</li>
                <li>If you wish to delete your RGM account and all synced history permanently, please contact the platform administrator. We will clear all of your data from Firestore within 7 business days.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">6. Policy Updates</h2>
              <p className="text-zinc-300">
                We may update this Privacy Policy from time to time to align with product updates or legal compliance. Any changes will be highlighted on the login screen or via app notifications.
              </p>

              <h2 className="text-xl font-bold text-white mt-8">7. Contact Us</h2>
              <p className="text-zinc-300">
                If you have questions about this policy or want to request account deletion, please email the platform administrator.
              </p>
            </>
          )}
        </article>
      </main>

      {/* Basic Footer */}
      <footer className="py-8 border-t border-white/5 text-center text-xs text-zinc-600 relative z-10">
        © 2026 RGM. All rights reserved.
      </footer>
    </div>
  );
}
