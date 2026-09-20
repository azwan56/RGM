"use client";

import Navbar from "@/components/Navbar";
import Link from "next/link";
import { useState } from "react";
import {
  BookOpen,
  User,
  Watch,
  Award,
  Heart,
  Target,
  HelpCircle,
  CheckCircle2,
  AlertTriangle,
  Lock,
  ArrowRight,
  Zap,
  Shield,
  ChevronRight,
  Sparkles,
  ExternalLink
} from "lucide-react";

export default function ManualPage() {
  const [activeSection, setActiveSection] = useState<string>("all");

  const sections = [
    { id: "step1", title: "1. 账号注册与登录", icon: User },
    { id: "step2", title: "2. 绑定手表导入历史", icon: Watch },
    { id: "step3", title: "3. 复旦戈大群准入与资料", icon: Award },
    { id: "step4", title: "4. 生理指标与配速测算", icon: Heart },
    { id: "step5", title: "5. 设立周/月/比赛目标", icon: Target },
    { id: "faq", title: "6. 常见问答与排错", icon: HelpCircle },
  ];

  function scrollToSection(id: string) {
    if (typeof document !== "undefined") {
      const el = document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth" });
      }
    }
  }

  return (
    <div className="min-h-screen bg-[#070708] text-white">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-10">
        {/* Hero Header */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#18181c] via-[#121215] to-[#0d0d10] border border-white/10 p-6 sm:p-10 shadow-2xl">
          <div className="absolute -right-12 -top-12 w-64 h-64 bg-[#FC4C02]/10 rounded-full blur-3xl pointer-events-none" />
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 relative z-10">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-[#FC4C02]/15 text-[#FC4C02] border border-[#FC4C02]/30">
                <BookOpen className="w-3.5 h-3.5" />
                <span>RGM 万跑跑团助手 · 官方新用户手册</span>
              </div>
              <h1 className="text-2xl sm:text-4xl font-black tracking-tight text-white">
                跑者快速上手与配置指南
              </h1>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-2xl leading-relaxed">
                只需 3 分钟，完成账号一键登录、手表数据直连、复旦戈大群准入核验与年度周月训练目标规划。
              </p>
            </div>

            <Link
              href="/dashboard/profile"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-2xl text-sm font-bold bg-[#FC4C02] hover:bg-[#ff5d1a] text-white shadow-lg shadow-[#FC4C02]/25 transition active:scale-95 shrink-0"
            >
              <span>前往完善个人档案</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Quick Anchor Pills */}
          <div className="flex flex-wrap gap-2 pt-6 mt-6 border-t border-white/5">
            {sections.map((sec) => {
              const Icon = sec.icon;
              return (
                <button
                  key={sec.id}
                  onClick={() => scrollToSection(sec.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-white/5 hover:bg-white/10 border border-white/5 text-zinc-300 hover:text-white transition"
                >
                  <Icon className="w-3.5 h-3.5 text-[#FC4C02]" />
                  <span>{sec.title}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── STEP 1: 账号注册与一键登录 ── */}
        <section id="step1" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-24">
          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 font-black">
              1
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">账号注册与一键登录</h2>
              <p className="text-xs text-zinc-400 mt-0.5">微信小程序与 Web 网页端数据全量打通、毫秒级实时同步</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">📱</span>
                <h3 className="text-sm font-bold text-white">微信小程序端（日常打卡与交流首选）</h3>
              </div>
              <ol className="text-xs text-zinc-400 space-y-2 list-decimal list-inside leading-relaxed">
                <li>在微信搜索小程序 **「万跑跑团助手」** 或扫描跑团邀请码/海报。</li>
                <li>点击底部导航栏最右侧的 **【我的】**。</li>
                <li>点击顶部醒目的 **【🟢 微信一键快速登录】** 按钮，授权完成账号建立。</li>
                <li>登录后点击顶部个人卡片，可随时修改自定义昵称与更换头像。</li>
              </ol>
            </div>

            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">💻</span>
                <h3 className="text-sm font-bold text-white">Web 网页管理端（大屏看板与深度分析）</h3>
              </div>
              <ol className="text-xs text-zinc-400 space-y-2 list-decimal list-inside leading-relaxed">
                <li>在电脑浏览器访问：<code className="text-amber-400 font-mono">https://rgm.vanpower.net</code></li>
                <li>支持点击“微信扫码登录”或输入账号密码直接登入。</li>
                <li>登入后自动同步您在小程序中的所有跑步打卡、手表绑定及跑团成员权限。</li>
              </ol>
            </div>
          </div>
        </section>

        {/* ── STEP 2: 绑定手表与导入历史 ── */}
        <section id="step2" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-24">
          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-[#0A84FF]/10 border border-[#0A84FF]/20 flex items-center justify-center text-[#0A84FF] font-black">
              2
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">绑定运动手表与导入运动历史</h2>
              <p className="text-xs text-zinc-400 mt-0.5">Garmin 佳明与 COROS 高驰官方数据直连，运动保存后 1~3 分钟自动出报告</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="text-blue-400 font-black">GARMIN</span> 佳明手表直连
                </span>
                <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20">双分区支持</span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                在【我的】→【👤 个人资料与账号】中找到“运动手表数据直连”，点击【绑定佳明账号】：
              </p>
              <ul className="text-xs text-zinc-400 space-y-1.5 list-disc list-inside">
                <li><strong className="text-white">分区选择</strong>：国内购买行货选“中国区 (garmin.cn)”；海外账号选“国际区 (garmin.com)”。</li>
                <li>输入 Garmin Connect 邮箱与密码完成安全认证。</li>
                <li>系统将自动开启后台静默同步，每次跑步结束自动推送打卡战报。</li>
              </ul>
            </div>

            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-white flex items-center gap-2">
                  <span className="text-[#FC4C02] font-black">COROS</span> 高驰手表直连
                </span>
                <span className="text-[10px] bg-orange-500/10 text-orange-400 px-2 py-0.5 rounded-full border border-orange-500/20">秒级同步</span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed">
                点击【绑定高驰账号】，输入 COROS App 注册的账号手机/邮箱与密码：
              </p>
              <ul className="text-xs text-zinc-400 space-y-1.5 list-disc list-inside">
                <li>绑定成功后，手表每次跑步完成将自动同步至个人运动记录。</li>
                <li>支持同步高驰体能负荷与心率数据。</li>
              </ul>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-200/90 leading-relaxed">
              <strong className="text-amber-300 font-bold block mb-0.5">⚡ 一键导入个人历史最好成绩 (PB)：</strong>
              绑定佳明后，请切换到【🏃 训练档案与赛事】标签页，在 PB 卡片点击<strong>【⚡ 从 Garmin 一键导入】</strong>，系统会自动抓取您历史上全马、半马、10公里、5公里的最快真实比赛/训练记录，无需手动反复输入！
            </div>
          </div>
        </section>

        {/* ── STEP 3: 加入复旦戈大群与资料规范 ── */}
        <section id="step3" className="bg-[#121215] border border-amber-500/30 rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 relative overflow-hidden scroll-mt-24">
          <div className="absolute top-0 right-0 w-80 h-80 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 font-black">
              3
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">加入“复旦戈”大群与个人实名资料规范</h2>
              <p className="text-xs text-zinc-400 mt-0.5">严格实施“2周实名核验准入制” · 关系到大团及所有从属跑团的访问权限</p>
            </div>
          </div>

          {/* Core Rule Alert */}
          <div className="p-5 rounded-2xl bg-rose-500/10 border border-rose-500/30 space-y-2">
            <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span>⚠️ 2 周准入限期铁律（必读）：</span>
            </div>
            <p className="text-xs text-rose-200/90 leading-relaxed">
              新加入“复旦戈”后进入 <strong>14 天临时访问期</strong>。队员必须在 14 天内，<strong>完整填写所有标有红星 * 的必填资料</strong>，并由复旦戈管理员在后台审核转正。
              <strong>若逾期未完成，系统将自动冻结暂停访问该大团以及该大团从属的所有跑团（如“复旦戈闵文跑团”）的一切看板、动态、打卡与活动！</strong>
            </p>
          </div>

          {/* Field Table */}
          <div className="space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Lock className="w-4 h-4 text-emerald-400" />
              <span>必填字段清单与 AES-256 高强度隐私保护机制</span>
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border border-white/10 rounded-2xl overflow-hidden">
                <thead className="bg-white/5 text-zinc-300 font-bold">
                  <tr>
                    <th className="p-3">字段名称</th>
                    <th className="p-3">类型</th>
                    <th className="p-3">填写用途</th>
                    <th className="p-3">隐私安全等级</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-zinc-400">
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">真实姓名 *</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold">大群必填</span></td>
                    <td className="p-3">戈友实名核实与赛事保险投保检录</td>
                    <td className="p-3 text-emerald-400">🔒 AES-256 加密。公开名册展示为脱敏姓名（如：张*、李*华）</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">生理性别 *</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold">大群必填</span></td>
                    <td className="p-3">戈赛男女名额配比与科学训练负荷计算</td>
                    <td className="p-3 text-zinc-300">公开可读（男/女）</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">出生日期 *</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold">大群必填</span></td>
                    <td className="p-3">自动测算实周岁、大师组/壮年组/青年组分级</td>
                    <td className="p-3 text-emerald-400">🔒 密文分级脱敏。公开名册绝不显示具体生日，仅显示组别</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">商学院项目 *</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold">大群必填</span></td>
                    <td className="p-3">下拉选择（中文EMBA、台大班、复旦-BI、奥林班等）</td>
                    <td className="p-3 text-zinc-300">校友项目归属与分班考核积分</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">所在班级/届别 *</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 text-[10px] font-bold">大群必填</span></td>
                    <td className="p-3">填写班级或期数（如：2022春2班、38期）</td>
                    <td className="p-3 text-zinc-300">班级战队凝聚与同班戈友互通</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">戈壁经历</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-white/10 text-zinc-300 text-[10px]">推荐选填</span></td>
                    <td className="p-3">选择“新戈”或“老戈（如戈20/戈21，A/B/C组）”</td>
                    <td className="p-3 text-zinc-300">教练团队针对性评估老戈传帮带与新戈进阶</td>
                  </tr>
                  <tr className="hover:bg-white/[0.02]">
                    <td className="p-3 font-bold text-white">联系手机 / 身份证号</td>
                    <td className="p-3"><span className="px-2 py-0.5 rounded bg-white/10 text-zinc-300 text-[10px]">安全保密</span></td>
                    <td className="p-3">越野拉练与团队赛事人身意外险投保保单必需</td>
                    <td className="p-3 text-emerald-400">🔒 仅大群超管可用于统一投保，普通跑友完全不可见</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-zinc-500">
              * 填毕后点击底部“💾 保存个人资料与账号设置”生效。若超期被暂停，补齐并保存后联系大群管理员点击【确认转正】即可瞬间恢复！
            </p>
          </div>
        </section>

        {/* ── STEP 4: 生理指标与配速测算 ── */}
        <section id="step4" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-24">
          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center text-rose-400 font-black">
              4
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">运动生理参数与 Canova 配速体系</h2>
              <p className="text-xs text-zinc-400 mt-0.5">驱动意大利 Renato Canova 经典马拉松/戈壁训练法精准运转的核心引擎</p>
            </div>
          </div>

          <div className="space-y-4">
            <p className="text-xs text-zinc-400 leading-relaxed">
              在【我的】页面切换至 **【🏃 训练档案与赛事】** 标签页：
            </p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <span className="text-base font-bold text-white block">1. VO2Max (最大摄氧量)</span>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  可点击右上角 <strong className="text-[#FC4C02]">【⚡ 依据 PB 测算】</strong>，系统基于丹尼尔斯 VDOT 曲线自动推算您的摄氧量天花板；亦可点击【从手表同步指标】抓取佳明/高驰测算值。
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <span className="text-base font-bold text-white block">2. 静息心率与最大心率</span>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  设定清晨静息心率与极限最大心率。系统以此划分有氧基础区、特异乳酸阈值区与无氧冲刺区，科学预警过度疲劳与心脏负荷。
                </p>
              </div>

              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
                <span className="text-base font-bold text-white block">3. 赋能 Canova 教练配速</span>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  完善生理参数后，进入【Canova教练】模块，系统将自动算出您今日训练专属的 6 级配速指导区间及赛后最佳超量恢复时间窗口。
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── STEP 5: 设立周计划、月计划与比赛目标 ── */}
        <section id="step5" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-24">
          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-[#FC4C02]/10 border border-[#FC4C02]/20 flex items-center justify-center text-[#FC4C02] font-black">
              5
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">设立训练目标与周/月计划</h2>
              <p className="text-xs text-zinc-400 mt-0.5">个人跑量规划 · 本周目标卡 · 目标赛事倒计时与 AI 赛事情报</p>
            </div>
          </div>

          <div className="space-y-6">
            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="text-base">📅</span>
                <span>2026 年度跑量与 12 个月阶梯规划</span>
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                在【🏃 训练档案与赛事】标签页中，您可灵活选择两种跑量规划模式：
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                <div className="p-3.5 rounded-xl bg-black/40 border border-white/5 text-xs text-zinc-300">
                  <strong className="text-white block mb-1">全年统一均值模式：</strong>
                  直接拖动滑动条设定（如每月 200 km），适合平时训练节奏稳定、常年坚持匀速有氧积累的跑者。
                </div>
                <div className="p-3.5 rounded-xl bg-black/40 border border-white/5 text-xs text-zinc-300">
                  <strong className="text-white block mb-1">按月自定义进阶模式：</strong>
                  可在 1~12 月逐月输入差异化目标（如冬训 150km → 春季戈赛选拔拉练 260km → 赛前 300km），系统自动汇总 2026 全年总目标。
                </div>
              </div>
            </div>

            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="text-base">🎯</span>
                <span>本周重点跑量目标卡（动态跟踪）</span>
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                点击快捷胶囊（30km、40km、50km、60km、70km+）或输入自定义数值，点击【单独保存周跑量目标】即可生效。小程序首页与网页看板将每日动态展示周达成率与环形进度条。
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-white/[0.02] border border-white/5 space-y-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <span className="text-base">🏁</span>
                <span>比赛日程管理、AI 赛事情报与完赛荣誉榜</span>
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed">
                点击【添加比赛计划】，录入戈壁挑战赛或马拉松赛事，设置优先级（A级核心大考、B级以赛代练）。系统将呈现开赛天数倒计时，并支持一键联网检索该赛事的<strong>赛道起伏海拔、累计爬升与关门时间</strong>。完赛后可上传现场靓照生成永久戈友荣誉战报！
              </p>
            </div>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section id="faq" className="bg-[#121215] border border-white/[0.08] rounded-3xl p-6 sm:p-8 shadow-xl space-y-6 scroll-mt-24">
          <div className="flex items-center gap-3 border-b border-white/5 pb-4">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 font-black">
              ?
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white">常见问题与排错 (FAQ)</h2>
              <p className="text-xs text-zinc-400 mt-0.5">高频问题一键自查与解决指南</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
              <h4 className="text-sm font-bold text-white">Q1: 为什么提示“跑团访问权限已暂停”？</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                解答：这说明您加入的跑团隶属于“复旦戈”大群，而您的大群 14 天临时访问期已到期，但个人实名资料中尚有标 * 必填项未填全，或管理员尚未确认。请进入【我的】→【👤 个人资料与账号】补齐并保存，之后联系大群管理员（或领队）点击【确认转正】即可即刻解冻恢复！
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
              <h4 className="text-sm font-bold text-white">Q2: 佳明手表跑步后，数据为什么没有同步过来？</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                解答：① 检查手机 Garmin Connect App 是否已完成手表蓝牙同步；② 检查手表直连卡片中服务器分区是否选对（国行设备请务必选择“中国区”）；③ 若曾修改佳明密码，请重新绑定一次账号凭证。
              </p>
            </div>

            <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/5 space-y-2">
              <h4 className="text-sm font-bold text-white">Q3: 填写真实姓名和身份证号码安全吗？</h4>
              <p className="text-xs text-zinc-400 leading-relaxed">
                解答：绝对安全。系统底层严格采用银行级 AES-256-GCM 高强度密文存储，普通跑友在团队名册中仅能看到脱敏星号姓名（如：张*、李*华）与年龄组别，绝无查看敏感明文权限。此外，在页面底部提供了【一键清除所有个人隐私数据】按钮，您随时可以彻底清除实名底账。
              </p>
            </div>
          </div>
        </section>

        {/* Bottom CTA */}
        <div className="text-center py-6">
          <Link
            href="/dashboard/profile"
            className="inline-flex items-center gap-2.5 px-8 py-4 rounded-2xl text-base font-bold bg-gradient-to-r from-[#FC4C02] to-[#ff7a45] text-white hover:brightness-110 shadow-xl shadow-[#FC4C02]/25 transition active:scale-95"
          >
            <span>立即前往完善个人档案与设置</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
