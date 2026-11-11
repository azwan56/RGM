"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Navbar from "@/components/Navbar";
import WeChatQrLoginPanel from "@/components/WeChatQrLoginPanel";
import { Mail, Lock, Smartphone, Watch, Globe, ShieldCheck, ArrowRight, QrCode } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"wechat" | "watch" | "email">("watch");

  // Watch Direct Login (COROS phone/email or Garmin phone/email)
  const [brand, setBrand] = useState<"coros" | "garmin">("coros");
  const [watchDomain, setWatchDomain] = useState<string>("teamcnapi.coros.com");
  const [watchAccount, setWatchAccount] = useState("");
  const [watchPassword, setWatchPassword] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaNotice, setMfaNotice] = useState("");

  // Email / Unified Account Login & Signup
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  function getPostLoginRedirect(): string {
    if (typeof window !== "undefined" && localStorage.getItem("rgm_pending_club_invite")) {
      return "/dashboard/team";
    }
    return "/dashboard";
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const mode = new URLSearchParams(window.location.search).get("mode");
      if (mode === "wechat" || mode === "watch" || mode === "email") {
        setTab(mode);
      }
    }
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session?.user) {
        router.push(getPostLoginRedirect());
      }
    });
  }, [router]);

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
        setMfaNotice(data.message || "已向您的注册手机或邮箱发送 6 位安全验证码，请输入验证码完成登录");
        return;
      }

      router.push(getPostLoginRedirect());
    } catch (err: any) {
      setErrorMsg(err.message || "手表账号验证失败，请核对手机号/邮箱与密码");
    } finally {
      setLoading(false);
    }
  }

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      if (isSignUp) {
        const { error } = await supabase.auth.signUp({
          email,
          password,
        });
        if (error) throw error;
        router.push(getPostLoginRedirect());
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        router.push(getPostLoginRedirect());
      }
    } catch (err: any) {
      setErrorMsg(err.message || "登录认证失败，请检查账号密码");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0c] text-white flex flex-col justify-between relative overflow-hidden">
      <Navbar />

      <div className="flex-1 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-[#121215] border border-white/10 rounded-3xl p-8 shadow-2xl space-y-5">
          <div className="text-center space-y-2">
            <img
              src="/logo.png"
              alt="万跑跑团助手 Logo"
              width={56}
              height={56}
              fetchPriority="high"
              className="w-14 h-14 rounded-2xl object-contain bg-white mx-auto shadow-lg shadow-[#FC4C02]/20"
            />
            <h1 className="text-2xl font-black text-white">
              {tab === "email" && isSignUp ? "创建万跑跑团助手账号" : "登录万跑跑团助手"}
            </h1>
            <p className="text-xs text-zinc-400">
              支持高驰手机号 / 佳明账号直接登录 · 与微信小程序数据实时互通
            </p>
          </div>

          {/* Auth Mode Tabs */}
          <div className="flex bg-white/5 p-1 rounded-2xl border border-white/5 gap-1">
            <button
              type="button"
              onClick={() => { setTab("wechat"); setErrorMsg(""); }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                tab === "wechat" ? "bg-[#07C160] text-white shadow-md" : "text-zinc-400 hover:text-white"
              }`}
            >
              <QrCode className="w-3.5 h-3.5 shrink-0" />
              微信扫码
            </button>
            <button
              type="button"
              onClick={() => { setTab("watch"); setErrorMsg(""); }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                tab === "watch" ? "bg-[#FC4C02] text-white shadow-md" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Watch className="w-3.5 h-3.5 shrink-0" />
              高驰 / 佳明直登
            </button>
            <button
              type="button"
              onClick={() => { setTab("email"); setErrorMsg(""); }}
              className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1 ${
                tab === "email" ? "bg-[#FC4C02] text-white shadow-md" : "text-zinc-400 hover:text-white"
              }`}
            >
              <Mail className="w-3.5 h-3.5 shrink-0" />
              邮箱 / 账号
            </button>
          </div>

          {errorMsg && (
            <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-200 leading-relaxed">
              {errorMsg}
            </div>
          )}

          {tab === "wechat" ? (
            <WeChatQrLoginPanel onSuccess={() => router.push(getPostLoginRedirect())} />
          ) : tab === "watch" ? (
            <form onSubmit={handleWatchAuth} className="space-y-4">
              {/* Brand Switcher */}
              <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-xl border border-white/10">
                <button
                  type="button"
                  onClick={() => switchBrand("coros")}
                  className={`py-2 rounded-lg text-xs font-bold transition-all ${
                    brand === "coros" ? "bg-emerald-600 text-white shadow" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  COROS 高驰（手机号/邮箱）
                </button>
                <button
                  type="button"
                  onClick={() => switchBrand("garmin")}
                  className={`py-2 rounded-lg text-xs font-bold transition-all ${
                    brand === "garmin" ? "bg-[#0A84FF] text-white shadow" : "text-zinc-400 hover:text-white"
                  }`}
                >
                  Garmin 佳明（手机号/邮箱）
                </button>
              </div>

              {needsMfa ? (
                <div className="space-y-4">
                  <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
                    <span className="text-amber-400 font-bold text-xs block mb-1">🔒 安全验证码确认</span>
                    <span className="text-xs text-zinc-300 block leading-relaxed">{mfaNotice}</span>
                  </div>
                  <div>
                    <label className="text-xs text-zinc-400 block mb-1.5">6 位短信 / 邮箱验证码</label>
                    <input
                      type="text"
                      required
                      maxLength={6}
                      value={mfaCode}
                      onChange={(e) => setMfaCode(e.target.value)}
                      placeholder="请输入 6 位验证码"
                      className="w-full bg-[#18181c] border border-amber-500/50 rounded-xl px-4 py-2.5 text-center text-lg tracking-widest font-mono text-white focus:outline-none focus:border-amber-400"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 hover:opacity-90 text-white font-bold rounded-xl text-sm transition-all shadow-lg shadow-[#FC4C02]/20 flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? "正在验证..." : "提交验证码并进入控制台"}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setNeedsMfa(false)}
                    className="w-full text-center text-xs text-zinc-400 hover:text-white"
                  >
                    返回修改账号密码
                  </button>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between text-xs text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Globe className="w-3.5 h-3.5" /> 账号所属区域
                    </span>
                    <div className="flex bg-white/5 p-0.5 rounded-lg border border-white/10">
                      {brand === "coros" ? (
                        <>
                          <button
                            type="button"
                            onClick={() => setWatchDomain("teamcnapi.coros.com")}
                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                              watchDomain === "teamcnapi.coros.com" ? "bg-white/15 text-white" : "text-zinc-400"
                            }`}
                          >
                            中国区（默认）
                          </button>
                          <button
                            type="button"
                            onClick={() => setWatchDomain("teamapi.coros.com")}
                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                              watchDomain === "teamapi.coros.com" ? "bg-white/15 text-white" : "text-zinc-400"
                            }`}
                          >
                            国际区
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            onClick={() => setWatchDomain("garmin.cn")}
                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                              watchDomain === "garmin.cn" ? "bg-white/15 text-white" : "text-zinc-400"
                            }`}
                          >
                            中国版 (garmin.cn)
                          </button>
                          <button
                            type="button"
                            onClick={() => setWatchDomain("garmin.com")}
                            className={`px-2.5 py-1 rounded-md text-[11px] font-bold ${
                              watchDomain === "garmin.com" ? "bg-white/15 text-white" : "text-zinc-400"
                            }`}
                          >
                            国际版 (garmin.com)
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-400 block mb-1.5">
                      {brand === "coros" ? "高驰账号（11位手机号 或 邮箱）" : "佳明账号（手机号 或 邮箱）"}
                    </label>
                    <div className="relative">
                      <Smartphone className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
                      <input
                        type="text"
                        required
                        value={watchAccount}
                        onChange={(e) => setWatchAccount(e.target.value)}
                        placeholder={brand === "coros" ? "直接输入高驰手机号（如 181xxxx）或邮箱" : "输入佳明邮箱或手机号"}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-400 block mb-1.5">
                      {brand === "coros" ? "高驰登录密码" : "佳明登录密码"}
                    </label>
                    <div className="relative">
                      <Lock className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
                      <input
                        type="password"
                        required
                        value={watchPassword}
                        onChange={(e) => setWatchPassword(e.target.value)}
                        placeholder={brand === "coros" ? "输入高驰 App 登录密码" : "输入佳明 Connect 登录密码"}
                        className="w-full bg-[#18181c] border border-white/10 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                      />
                    </div>
                  </div>

                  <div className="flex items-start gap-2 p-2.5 bg-white/[0.03] rounded-xl border border-white/5 text-[11px] text-zinc-400 leading-relaxed">
                    <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                    <span>已在微信小程序绑定过手表的跑友，输入手机号与手表密码即可直接进入同一跑者档案，无需注册邮箱。</span>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 hover:opacity-90 text-white font-bold rounded-xl text-sm transition-all shadow-lg shadow-[#FC4C02]/20 flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? "正在验证..." : "验证并进入数据控制台"}
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </>
              )}
            </form>
          ) : (
            <form onSubmit={handleAuth} className="space-y-4">
              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">
                  {isSignUp ? "注册邮箱地址" : "手机号 / 邮箱 / 手表绑定账号"}
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
                  <input
                    type={isSignUp ? "email" : "text"}
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={isSignUp ? "runner@example.com" : "输入手机号（如 181xxxx）或邮箱"}
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-zinc-400 block mb-1.5">密码</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isSignUp ? "至少 6 位字符" : "输入登录密码或绑定的手表密码"}
                    className="w-full bg-[#18181c] border border-white/10 rounded-xl pl-10 pr-3.5 py-2.5 text-sm text-white focus:outline-none focus:border-[#FC4C02]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 hover:opacity-90 text-white font-bold rounded-xl text-sm transition-all shadow-lg shadow-[#FC4C02]/20 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {loading ? "正在处理..." : isSignUp ? "立即注册" : "进入数据控制台"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}

          <div className="pt-4 border-t border-white/5 flex items-center justify-between text-xs text-zinc-400">
            {tab === "email" ? (
              <button
                type="button"
                onClick={() => setIsSignUp(!isSignUp)}
                className="text-[#FC4C02] hover:underline"
              >
                {isSignUp ? "已有账号？直接登录" : "没有邮箱账号？免费注册"}
              </button>
            ) : (
              <span className="text-zinc-500">支持高驰 / 佳明双区直连</span>
            )}

            <Link href="/" className="hover:text-white transition-colors">
              返回官网首页
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
