"use client";

import { useState } from "react";
import Link from "next/link";

type Lang = "zh" | "en";

export default function TermsOfService() {
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
                服务条款 (Terms of Service)
              </h1>
              <p className="text-xs text-zinc-500">最近更新日期：2026年7月14日</p>

              <p className="text-zinc-300 leading-relaxed mt-4">
                欢迎阅读并使用 <strong>RGM (跑团管理平台)</strong> 服务条款。一旦您访问本网站、完成账号注册或绑定 Strava，即表示您已阅读、理解并同意接受本条款的约束。
              </p>

              <hr className="border-white/10 my-6" />

              <h2 className="text-xl font-bold text-white mt-8">1. 接受服务条款</h2>
              <p className="text-zinc-300">
                本条款适用于所有访问或使用 RGM 平台的用户。如果您不同意本条款的任何部分，请立即停止使用或注销您的账号。
              </p>

              <h2 className="text-xl font-bold text-white mt-8">2. 账户注册与安全性</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>您保证注册时填写的邮箱信息真实有效，并对您账户下的所有活动以及密码安全负全部责任。</li>
                <li>您同意在发现任何未经授权的账户访问或安全漏洞时，立即通知平台管理员。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">3. 服务内容与授权</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>RGM 是一项用于连接运动数据（如 Strava 和 Google Health）、自动分析体能指数（CTL/ATL/TSB/VDOT）和组织跑团内部排行榜的社区管理服务。</li>
                <li>为了同步运动数据，您需要主动授权您的 Strava 或 Google 账号。您随时可以通过 Strava 或 Google 撤销对此平台的访问权限。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">4. 用户行为规范与诚信守则</h2>
              <p className="text-zinc-300">
                本平台是跑友们良性竞争和自我提升的场所。您在使用排行榜、团队等社交功能时，应遵守以下规范：
              </p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li><strong>杜绝运动造假</strong>：您同意仅上传真实的跑步运动记录。严禁通过骑车伪装成跑步、篡改 GPS 文件、使用他人记录或任何其他手段作弊来刷高跑团排行榜。</li>
                <li><strong>文明互动</strong>：不得利用团队名、昵称、Discord 机器人通知等平台渠道散布辱骂、淫秽、人身攻击或任何违反当地法律法规的信息。</li>
                <li>对于违反诚信守则或滥用服务的用户，平台管理员保留随时暂停或终止其账户且不承担任何责任的权利。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">5. 体育科学免责声明</h2>
              <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4 text-zinc-300 text-sm leading-relaxed my-4">
                <strong>重要提醒：</strong> RGM 提供的所有生理指标（包括但不限于 CTL 体能值、ATL 疲劳值、TSB 状态值、VDOT 跑力值）以及 AI 教练所给出的训练指导意见，均是基于运动学公式与数据模型的<strong>估算与推测，不构成医疗、诊断、康复或专业运动医学建议</strong>。在开始任何高强度马拉松备赛训练计划之前，请咨询专业医生或专业教练的意见。用户应根据自身身体状况合理安排训练，本平台不对任何因过度训练或运动受伤等导致的健康问题承担任何法律责任。
              </div>

              <h2 className="text-xl font-bold text-white mt-8">6. 知识产权与服务修改</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>RGM 平台的全部代码、UI 设计、AI 提示词逻辑及内容均归平台所有或已获合法授权。</li>
                <li>我们保留随时调整、暂停或终止平台部分或全部服务的权利，届时会尽量提前在平台通知。</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">7. 责任限制</h2>
              <p className="text-zinc-300">
                在法律允许的最大范围内，RGM 及其开发者不因任何数据同步延迟、API 服务不可用（如 Strava 接口限流）、或第三方故障导致的任何直接或间接损害承担责任。
              </p>

              <h2 className="text-xl font-bold text-white mt-8">8. 适用法律与争议解决</h2>
              <p className="text-zinc-300">
                本服务条款受现行法律管辖并按其解释。因本条款产生的任何争议，双方应友好协商解决。
              </p>
            </>
          ) : (
            // ── ENGLISH VERSION ──────────────────────────────────────────────
            <>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-2">
                Terms of Service
              </h1>
              <p className="text-xs text-zinc-500">Last Updated: July 14, 2026</p>

              <p className="text-zinc-300 leading-relaxed mt-4">
                Please read these Terms of Service carefully before using <strong>RGM (Running Community Manager)</strong>. By accessing this website, registering an account, or connecting to Strava, you agree to be bound by these terms.
              </p>

              <hr className="border-white/10 my-6" />

              <h2 className="text-xl font-bold text-white mt-8">1. Acceptance of Terms</h2>
              <p className="text-zinc-300">
                These terms apply to all users who access or use the RGM platform. If you do not agree with any part of these terms, please stop using the service and delete your account immediately.
              </p>

              <h2 className="text-xl font-bold text-white mt-8">2. Account Registration and Security</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>You guarantee that the email address provided during registration is accurate and valid, and you are fully responsible for all activities under your account and password.</li>
                <li>You agree to notify the platform administrator immediately of any unauthorized access or breach of security.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">3. Services and Authorization</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>RGM is a community management service that integrates sports wearable data (such as Strava and Google Health) to calculate sports science indices (CTL/ATL/TSB/VDOT) and maintain running team leaderboards.</li>
                <li>To sync your workouts, you must authorize this platform to access your Strava or Google account. You may revoke this access at any time through your Strava or Google account settings.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">4. User Conduct and Integrity Code</h2>
              <p className="text-zinc-300">
                This platform is designed for friendly competition and personal growth. When using community and leaderboard features, you agree to follow these rules:
              </p>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li><strong>No Cheating</strong>: You agree to upload only authentic running logs. Cheat activities—such as pretending to run while cycling, spoofing GPS files, or using other users' records—are strictly prohibited.</li>
                <li><strong>Respectful Interaction</strong>: You must not use team names, usernames, or bot notification channels to post abusive, obscene, or offensive content that violates local regulations.</li>
                <li>The administrator reserves the right to suspend or terminate accounts that breach the Integrity Code without prior notice or liability.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">5. Sports Science Disclaimer</h2>
              <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-4 text-zinc-300 text-sm leading-relaxed my-4">
                <strong>Important Notice:</strong> All physical metrics (such as CTL, ATL, TSB, VDOT) and AI Coach guidelines provided on RGM are based on kinematics models and mathematical estimations. **They do not constitute medical, diagnostic, rehabilitative, or professional sports medicine advice.** Please consult a qualified physician or professional running coach before beginning any high-intensity marathon training program. The platform does not assume any liability for injuries or health issues resulting from training activities.
              </div>

              <h2 className="text-xl font-bold text-white mt-8">6. Intellectual Property & Modifications</h2>
              <ul className="list-disc pl-6 space-y-2 text-zinc-300">
                <li>All source code, UI designs, AI prompt engineering, and core content of RGM are owned by the platform or licensed legally.</li>
                <li>We reserve the right to modify, suspend, or terminate the services at any time, with reasonable prior notice when feasible.</li>
              </ul>

              <h2 className="text-xl font-bold text-white mt-8">7. Limitation of Liability</h2>
              <p className="text-zinc-300">
                To the maximum extent permitted by law, RGM and its developers are not liable for any direct or indirect damages caused by data sync delays, API rate-limiting (e.g. Strava API limits), or third-party outages.
              </p>

              <h2 className="text-xl font-bold text-white mt-8">8. Governing Law & Dispute Resolution</h2>
              <p className="text-zinc-300">
                These terms are governed by and construed in accordance with applicable laws. Any dispute arising from these terms shall be resolved through friendly consultations.
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
