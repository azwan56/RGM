"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import WeChatQrLoginPanel from "@/components/WeChatQrLoginPanel";
import {
  ArrowRight,
  Globe,
  Lock,
  Mail,
  QrCode,
  ShieldCheck,
  Smartphone,
  Watch,
} from "lucide-react";

interface AuthCockpitPanelProps {
  initialTab?: "wechat" | "watch" | "email";
  onSuccess: () => void;
  showHeader?: boolean;
}

export default function AuthCockpitPanel({
  initialTab = "watch",
  onSuccess,
  showHeader = true,
}: AuthCockpitPanelProps) {
  const [tab, setTab] = useState<"wechat" | "watch" | "email">(initialTab);
  const [brand, setBrand] = useState<"coros" | "garmin">("garmin");
  const [watchDomain, setWatchDomain] = useState<string>("garmin.cn");
  const [watchAccount, setWatchAccount] = useState("");
  const [watchPassword, setWatchPassword] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaNotice, setMfaNotice] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);

  function switchBrand(nextBrand: "coros" | "garmin") {
    setBrand(nextBrand);
    setWatchDomain(nextBrand === "coros" ? "teamcnapi.coros.com" : "garmin.cn");
    setNeedsMfa(false);
    setMfaCode("");
    setErrorMsg("");
  }

  async function handleWatchAuth(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const { data, error } = await supabase.auth.signInWithWatch({
        brand,
        account: watchAccount,
        password: watchPassword,
        domain: watchDomain,
        mfaCode: needsMfa ? mfaCode : undefined,
      });
      if (error) throw error;
      if (data?.needsMfa) {
        setNeedsMfa(true);
        setMfaNotice(
          data.message || "已向您的注册手机或邮箱发送 6 位安全验证码，请输入验证码完成登录"
        );
        return;
      }
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || "手表账号验证失败，请核对手机号/邮箱与密码");
    } finally {
      setLoading(false);
    }
  }

  async function handleEmailAuth(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message || "登录认证失败，请检查账号密码");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-3xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] border-t-[3px] border-t-[#FC4C02] p-6 sm:p-7 shadow-2xl space-y-5">
      {showHeader && (
        <div className="space-y-1">
          <h2 className="text-xl font-black text-[var(--rgm-text)]">
            {tab === "email" && isSignUp ? "创建万跑跑团助手账号" : "登录万跑工作台"}
          </h2>
          <p className="text-xs text-[var(--rgm-text-muted)]">
            免注册 · 使用微信扫码或运动手表账号直连即刻同步
          </p>
        </div>
      )}

      {/* 3-in-1 Auth Mode Tabs */}
      <div className="grid grid-cols-3 gap-1 p-1 rounded-2xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
        <button
          type="button"
          onClick={() => {
            setTab("wechat");
            setErrorMsg("");
          }}
          className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 cursor-pointer ${
            tab === "wechat"
              ? "bg-emerald-600 text-white shadow-sm"
              : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
          }`}
        >
          <QrCode className="w-3.5 h-3.5 shrink-0" />
          微信扫码
        </button>
        <button
          type="button"
          onClick={() => {
            setTab("watch");
            setErrorMsg("");
          }}
          className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 cursor-pointer ${
            tab === "watch"
              ? "bg-[#FC4C02] text-white shadow-sm"
              : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
          }`}
        >
          <Watch className="w-3.5 h-3.5 shrink-0" />
          手表直连
        </button>
        <button
          type="button"
          onClick={() => {
            setTab("email");
            setErrorMsg("");
          }}
          className={`py-2 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1 cursor-pointer ${
            tab === "email"
              ? "bg-[#FC4C02] text-white shadow-sm"
              : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
          }`}
        >
          <Mail className="w-3.5 h-3.5 shrink-0" />
          邮箱账号
        </button>
      </div>

      {errorMsg && (
        <div className="p-3 bg-[var(--rgm-red-tint)] border border-rose-500/35 rounded-xl text-xs text-rose-500 leading-relaxed font-medium">
          {errorMsg}
        </div>
      )}

      {tab === "wechat" ? (
        <WeChatQrLoginPanel onSuccess={onSuccess} />
      ) : tab === "watch" ? (
        <form onSubmit={handleWatchAuth} className="space-y-4">
          {/* Watch Brand Cards (COROS / Garmin) */}
          <div className="space-y-1.5">
            <div className="text-[11px] font-bold text-[var(--rgm-text-2)]">选择运动手表品牌</div>
            <div className="grid grid-cols-2 gap-2.5">
              <button
                type="button"
                onClick={() => switchBrand("coros")}
                className={`p-2.5 rounded-xl border text-center transition cursor-pointer ${
                  brand === "coros"
                    ? "bg-[var(--rgm-green-tint)] border-emerald-500 text-emerald-500"
                    : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
                }`}
              >
                <div className="text-xs font-extrabold">COROS 高驰</div>
                <div className="text-[10px] opacity-80 mt-0.5">中国 / 国际账号</div>
              </button>
              <button
                type="button"
                onClick={() => switchBrand("garmin")}
                className={`p-2.5 rounded-xl border text-center transition cursor-pointer ${
                  brand === "garmin"
                    ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02] text-[#FC4C02]"
                    : "bg-[var(--rgm-card-2)] border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
                }`}
              >
                <div className="text-xs font-extrabold">Garmin 佳明</div>
                <div className="text-[10px] opacity-80 mt-0.5">推荐 · 双区直连</div>
              </button>
            </div>
          </div>

          {needsMfa ? (
            <div className="space-y-3.5">
              <div className="p-3.5 bg-[var(--rgm-amber-tint)] border border-amber-500/40 rounded-2xl">
                <div className="text-amber-500 font-bold text-xs mb-1">
                  MFA 两步安全验证
                </div>
                <div className="text-xs text-[var(--rgm-text-2)] leading-relaxed">{mfaNotice}</div>
              </div>
              <div>
                <label className="text-xs text-[var(--rgm-text-2)] block mb-1.5 font-semibold">
                  6 位安全验证码
                </label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value)}
                  placeholder="请输入 6 位验证码"
                  className="w-full bg-[var(--rgm-card-2)] border border-amber-500/50 rounded-xl px-4 py-2.5 text-center text-lg tracking-widest font-mono text-[var(--rgm-text)] focus:outline-none focus:border-[#FC4C02]"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-[#FC4C02] hover:bg-orange-600 text-white font-bold rounded-xl text-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer shadow-lg shadow-[#FC4C02]/20"
              >
                {loading ? "正在验证..." : "提交验证码并进入工作台"}
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setNeedsMfa(false)}
                className="w-full text-center text-xs text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer"
              >
                返回修改账号密码
              </button>
            </div>
          ) : (
            <>
              {/* Server Zone Toggle */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-[11px] text-[var(--rgm-text-2)] font-bold">
                  <span className="flex items-center gap-1">
                    <Globe className="w-3.5 h-3.5" /> 服务器分区
                  </span>
                  <span className="text-[10px] text-[var(--rgm-text-muted)]">国内行货选中国区</span>
                </div>
                <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
                  {brand === "garmin" ? (
                    <>
                      <button
                        type="button"
                        onClick={() => setWatchDomain("garmin.cn")}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                          watchDomain === "garmin.cn"
                            ? "bg-[var(--rgm-blue-tint)] text-sky-500 border border-sky-500/40"
                            : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
                        }`}
                      >
                        中国区 (garmin.cn)
                      </button>
                      <button
                        type="button"
                        onClick={() => setWatchDomain("garmin.com")}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                          watchDomain === "garmin.com"
                            ? "bg-[var(--rgm-blue-tint)] text-sky-500 border border-sky-500/40"
                            : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
                        }`}
                      >
                        国际区 (garmin.com)
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => setWatchDomain("teamcnapi.coros.com")}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                          watchDomain === "teamcnapi.coros.com"
                            ? "bg-[var(--rgm-blue-tint)] text-sky-500 border border-sky-500/40"
                            : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
                        }`}
                      >
                        高驰中国区（默认）
                      </button>
                      <button
                        type="button"
                        onClick={() => setWatchDomain("teamapi.coros.com")}
                        className={`py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                          watchDomain === "teamapi.coros.com"
                            ? "bg-[var(--rgm-blue-tint)] text-sky-500 border border-sky-500/40"
                            : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
                        }`}
                      >
                        高驰国际区
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className="space-y-2.5">
                <div className="relative">
                  <Smartphone className="w-4 h-4 text-[var(--rgm-text-muted)] absolute left-3.5 top-3" />
                  <input
                    type="text"
                    required
                    value={watchAccount}
                    onChange={(e) => setWatchAccount(e.target.value)}
                    placeholder={
                      brand === "coros"
                        ? "高驰手机号（如 181xxxx）或邮箱"
                        : "佳明账号（邮箱或手机号）"
                    }
                    className="w-full bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-[var(--rgm-text)] focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[var(--rgm-text-muted)] absolute left-3.5 top-3" />
                  <input
                    type="password"
                    required
                    value={watchPassword}
                    onChange={(e) => setWatchPassword(e.target.value)}
                    placeholder={
                      brand === "coros" ? "高驰登录密码" : "佳明 Connect 登录密码"
                    }
                    className="w-full bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] rounded-xl pl-10 pr-20 py-2.5 text-sm text-[var(--rgm-text)] focus:outline-none focus:border-[#FC4C02]"
                  />
                  <span className="absolute right-2.5 top-2 px-2 py-0.5 rounded-md bg-[var(--rgm-green-tint)] text-emerald-500 text-[10px] font-bold">
                    已加密
                  </span>
                </div>
              </div>

              <div className="flex items-start gap-2 p-2.5 bg-[var(--rgm-card-2)] rounded-xl border border-[var(--rgm-border)] text-[11px] text-[var(--rgm-text-2)] leading-relaxed">
                <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                <span>
                  已在微信小程序绑过手表的跑友，输入手机号与手表密码即可直达同一档案，无需重复注册。
                </span>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-[#FC4C02] hover:bg-orange-600 text-white font-bold rounded-xl text-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer shadow-lg shadow-[#FC4C02]/20"
              >
                {loading ? "正在验证..." : "验证并进入桌面工作台"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </>
          )}
        </form>
      ) : (
        <form onSubmit={handleEmailAuth} className="space-y-3.5">
          <div>
            <label className="text-xs text-[var(--rgm-text-2)] block mb-1.5 font-semibold">
              {isSignUp ? "注册邮箱地址" : "手机号 / 邮箱 / 手表绑定账号"}
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-[var(--rgm-text-muted)] absolute left-3.5 top-3" />
              <input
                type={isSignUp ? "email" : "text"}
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={isSignUp ? "runner@example.com" : "输入手机号（如 181xxxx）或邮箱"}
                className="w-full bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-[var(--rgm-text)] focus:outline-none focus:border-[#FC4C02]"
              />
            </div>
          </div>

          <div>
            <label className="text-xs text-[var(--rgm-text-2)] block mb-1.5 font-semibold">
              密码
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-[var(--rgm-text-muted)] absolute left-3.5 top-3" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={isSignUp ? "至少 6 位字符" : "输入登录密码或手表密码"}
                className="w-full bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-[var(--rgm-text)] focus:outline-none focus:border-[#FC4C02]"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#FC4C02] hover:bg-orange-600 text-white font-bold rounded-xl text-sm transition flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer shadow-lg shadow-[#FC4C02]/20"
          >
            {loading ? "正在处理..." : isSignUp ? "立即注册并进入" : "进入桌面工作台"}
            <ArrowRight className="w-4 h-4" />
          </button>

          <div className="text-right">
            <button
              type="button"
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-xs font-semibold text-[#FC4C02] hover:underline cursor-pointer"
            >
              {isSignUp ? "已有账号？直接登录" : "没有邮箱账号？免费注册"}
            </button>
          </div>
        </form>
      )}

      {/* Footer Quick Onboarding Hint */}
      <div className="pt-3 border-t border-[var(--rgm-border)] flex items-center justify-between gap-2 text-[11px] text-[var(--rgm-text-muted)]">
        <span className="truncate">暂无手表？登录后 3 步填成绩秒算 VDOT 课表</span>
        <Link href="/dashboard/manual" className="text-[#FC4C02] font-bold shrink-0 hover:underline">
          帮助手册 ›
        </Link>
      </div>
    </div>
  );
}
