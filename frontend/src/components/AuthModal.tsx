"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { auth } from "@/lib/firebase";
import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  RecaptchaVerifier,
  signInWithPhoneNumber,
  ConfirmationResult,
} from "firebase/auth";

// ── Types ────────────────────────────────────────────────────────────────────
type Screen = "select" | "email" | "phone";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function AuthModal({ open, onClose, onSuccess }: AuthModalProps) {
  const [screen, setScreen] = useState<Screen>("select");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Email state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);

  // Phone state
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const confirmationRef = useRef<ConfirmationResult | null>(null);
  const recaptchaRef = useRef<RecaptchaVerifier | null>(null);
  const recaptchaContainerRef = useRef<HTMLDivElement | null>(null);

  // Reset everything when modal closes or screen changes
  const resetAll = useCallback(() => {
    setError("");
    setLoading(false);
    setEmail("");
    setPassword("");
    setIsRegister(false);
    setPhone("");
    setOtp("");
    setOtpSent(false);
    setCountdown(0);
    confirmationRef.current = null;
    if (recaptchaRef.current) {
      recaptchaRef.current.clear();
      recaptchaRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!open) {
      resetAll();
      setScreen("select");
    }
  }, [open, resetAll]);

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0) return;
    const t = setInterval(() => setCountdown((c) => c - 1), 1000);
    return () => clearInterval(t);
  }, [countdown]);

  const handleSuccess = useCallback(() => {
    onClose();
    onSuccess?.();
  }, [onClose, onSuccess]);

  const goBack = () => {
    setScreen("select");
    setError("");
  };

  // ── Google ────────────────────────────────────────────────────────────────
  const handleGoogle = async () => {
    setError("");
    setLoading(true);
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
      handleSuccess();
    } catch (e: any) {
      if (e.code !== "auth/popup-closed-by-user") {
        setError(mapError(e.code));
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Email / Password ──────────────────────────────────────────────────────
  const handleEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email) { setError("请输入邮箱地址"); return; }
    if (password.length < 6) { setError("密码至少 6 位"); return; }
    setLoading(true);
    try {
      if (isRegister) {
        await createUserWithEmailAndPassword(auth, email, password);
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
      handleSuccess();
    } catch (e: any) {
      setError(mapError(e.code));
    } finally {
      setLoading(false);
    }
  };

  // ── Phone ─────────────────────────────────────────────────────────────────
  const setupRecaptcha = () => {
    if (recaptchaRef.current) {
      recaptchaRef.current.clear();
      recaptchaRef.current = null;
    }
    if (recaptchaContainerRef.current) {
      recaptchaContainerRef.current.innerHTML = "";
    }
    recaptchaRef.current = new RecaptchaVerifier(auth, "recaptcha-container", {
      size: "invisible",
    });
  };

  const handleSendOtp = async () => {
    setError("");
    const cleaned = phone.trim();
    if (!cleaned) { setError("请输入手机号"); return; }
    const fullPhone = cleaned.startsWith("+") ? cleaned : `+86${cleaned}`;
    setLoading(true);
    try {
      setupRecaptcha();
      const result = await signInWithPhoneNumber(auth, fullPhone, recaptchaRef.current!);
      confirmationRef.current = result;
      setOtpSent(true);
      setCountdown(60);
    } catch (e: any) {
      setError(mapError(e.code));
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (otp.length < 6) { setError("请输入 6 位验证码"); return; }
    if (!confirmationRef.current) { setError("验证会话已过期，请重新获取"); return; }
    setLoading(true);
    try {
      await confirmationRef.current.confirm(otp);
      handleSuccess();
    } catch (e: any) {
      setError(mapError(e.code));
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" style={{ animation: "fadeIn 0.2s ease-out" }} />

      {/* Card */}
      <div
        className="relative w-full max-w-sm bg-[#141414] border border-white/10 rounded-2xl shadow-2xl shadow-black/60 overflow-hidden"
        style={{ animation: "slideUp 0.28s ease-out" }}
      >
        {/* Close */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-zinc-500 hover:text-white transition-colors"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>

        {/* Back button (non-select screens) */}
        {screen !== "select" && (
          <button
            onClick={goBack}
            className="absolute top-4 left-4 z-10 flex items-center gap-1.5 text-xs text-zinc-500 hover:text-white transition-colors"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            返回
          </button>
        )}

        <div className="px-7 pt-8 pb-7">
          {/* ── SELECT SCREEN ─────────────────────────────────────────── */}
          {screen === "select" && (
            <>
              <div className="text-center mb-7">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#FC4C02]/15 border border-[#FC4C02]/30 mb-4">
                  <svg className="w-6 h-6 text-[#FC4C02]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                    <circle cx="12" cy="8" r="4" />
                    <path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
                  </svg>
                </div>
                <h2 className="text-xl font-bold text-white">欢迎加入 <span className="text-[#FC4C02]">RGM</span></h2>
                <p className="text-sm text-zinc-500 mt-1">请选择登录或注册方式</p>
              </div>

              <div className="space-y-3">
                {/* Google */}
                <button
                  onClick={handleGoogle}
                  disabled={loading}
                  className="w-full flex items-center gap-4 px-4 py-3.5 bg-white hover:bg-zinc-100 text-black font-semibold rounded-xl transition-all disabled:opacity-50 group"
                >
                  <span className="w-9 h-9 flex items-center justify-center rounded-lg bg-white shadow-sm border border-zinc-200 shrink-0">
                    <GoogleIcon />
                  </span>
                  <span className="flex-1 text-left text-sm">
                    {loading ? "跳转中..." : "使用 Gmail / Google 账号"}
                  </span>
                  <svg className="w-4 h-4 text-zinc-400 group-hover:text-zinc-600 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>

                {/* Email */}
                <button
                  onClick={() => setScreen("email")}
                  className="w-full flex items-center gap-4 px-4 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white font-semibold rounded-xl transition-all group"
                >
                  <span className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/8 border border-white/10 shrink-0">
                    <svg className="w-4.5 h-4.5 text-zinc-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                      <rect x="2" y="4" width="20" height="16" rx="2" />
                      <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
                    </svg>
                  </span>
                  <span className="flex-1 text-left text-sm">邮箱登录 / 注册</span>
                  <svg className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>

                {/* Phone */}
                <button
                  onClick={() => setScreen("phone")}
                  className="w-full flex items-center gap-4 px-4 py-3.5 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-white font-semibold rounded-xl transition-all group"
                >
                  <span className="w-9 h-9 flex items-center justify-center rounded-lg bg-white/8 border border-white/10 shrink-0">
                    <svg className="w-4.5 h-4.5 text-zinc-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
                      <rect x="5" y="2" width="14" height="20" rx="2" />
                      <path d="M12 18h.01" />
                    </svg>
                  </span>
                  <span className="flex-1 text-left text-sm">手机短信验证码</span>
                  <svg className="w-4 h-4 text-zinc-600 group-hover:text-zinc-400 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>

              <p className="text-center text-xs text-zinc-600 mt-6">
                注册即表示同意服务条款与隐私政策
              </p>
            </>
          )}

          {/* ── EMAIL SCREEN ───────────────────────────────────────────── */}
          {screen === "email" && (
            <>
              <div className="text-center mb-6 mt-2">
                <h2 className="text-lg font-bold text-white">
                  {isRegister ? "创建新账号" : "邮箱登录"}
                </h2>
                <p className="text-sm text-zinc-500 mt-1">使用邮箱和密码</p>
              </div>

              {error && <ErrorBanner>{error}</ErrorBanner>}

              <form onSubmit={handleEmail} className="space-y-4">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1.5 font-medium">邮箱地址</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    autoComplete="email"
                    autoFocus
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1.5 font-medium">密码</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="至少 6 位"
                    autoComplete={isRegister ? "new-password" : "current-password"}
                    className={inputCls}
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className={primaryBtn}
                >
                  {loading ? <Spinner /> : isRegister ? "注册新账号" : "登录"}
                </button>
              </form>

              <div className="mt-5 flex items-center gap-3">
                <div className="flex-1 h-px bg-white/8" />
                <span className="text-xs text-zinc-600">{isRegister ? "已有账号？" : "还没有账号？"}</span>
                <div className="flex-1 h-px bg-white/8" />
              </div>
              <button
                onClick={() => { setIsRegister(!isRegister); setError(""); }}
                className="mt-3 w-full py-2.5 rounded-xl border border-white/10 hover:border-white/20 text-sm text-zinc-300 hover:text-white font-medium transition-all"
              >
                {isRegister ? "去登录" : "创建新账号"}
              </button>
            </>
          )}

          {/* ── PHONE SCREEN ───────────────────────────────────────────── */}
          {screen === "phone" && (
            <>
              <div className="text-center mb-6 mt-2">
                <h2 className="text-lg font-bold text-white">手机验证码登录</h2>
                <p className="text-sm text-zinc-500 mt-1">
                  {otpSent ? `验证码已发送至 ${phone.startsWith("+") ? phone : "+86" + phone}` : "输入手机号获取短信验证码"}
                </p>
              </div>

              {error && <ErrorBanner>{error}</ErrorBanner>}

              {!otpSent ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1.5 font-medium">手机号码</label>
                    <div className="flex gap-2">
                      <span className="flex items-center justify-center px-3.5 bg-white/5 border border-white/10 rounded-xl text-zinc-400 text-sm shrink-0 font-mono">
                        +86
                      </span>
                      <input
                        type="tel"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value.replace(/[^\d+]/g, ""))}
                        placeholder="138 0000 0000"
                        autoComplete="tel"
                        autoFocus
                        className={`${inputCls} flex-1`}
                      />
                    </div>
                    <p className="mt-1.5 text-xs text-zinc-600">含国际区号可直接输入，如 +65 XXXX XXXX</p>
                  </div>
                  <button
                    onClick={handleSendOtp}
                    disabled={loading}
                    className={primaryBtn}
                  >
                    {loading ? <Spinner /> : "获取验证码"}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleVerifyOtp} className="space-y-4">
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1.5 font-medium">短信验证码</label>
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      value={otp}
                      onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                      placeholder="● ● ● ● ● ●"
                      autoComplete="one-time-code"
                      autoFocus
                      className={`${inputCls} tracking-[0.6em] text-center text-lg font-mono`}
                    />
                  </div>
                  <button type="submit" disabled={loading} className={primaryBtn}>
                    {loading ? <Spinner /> : "验证并登录"}
                  </button>
                  <div className="flex items-center justify-between text-xs pt-1">
                    <button
                      type="button"
                      onClick={() => { setOtpSent(false); setOtp(""); setError(""); }}
                      className="text-zinc-500 hover:text-zinc-300 transition-colors"
                    >
                      ← 更换号码
                    </button>
                    <button
                      type="button"
                      onClick={handleSendOtp}
                      disabled={countdown > 0 || loading}
                      className="text-[#FC4C02] hover:text-orange-400 disabled:text-zinc-600 disabled:cursor-not-allowed transition-colors font-medium"
                    >
                      {countdown > 0 ? `重新发送 (${countdown}s)` : "重新发送"}
                    </button>
                  </div>
                </form>
              )}
              <div id="recaptcha-container" ref={recaptchaContainerRef} />
            </>
          )}
        </div>
      </div>

      <style jsx>{`
        @keyframes fadeIn  { from { opacity: 0 } to { opacity: 1 } }
        @keyframes slideUp { from { opacity: 0; transform: translateY(20px) scale(0.97) } to { opacity: 1; transform: translateY(0) scale(1) } }
      `}</style>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────
const inputCls = "w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder-zinc-600 focus:outline-none focus:border-[#FC4C02]/50 focus:ring-1 focus:ring-[#FC4C02]/25 transition-all text-sm";
const primaryBtn = "w-full py-3.5 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-semibold rounded-xl hover:shadow-lg hover:shadow-[#FC4C02]/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm flex items-center justify-center";

function ErrorBanner({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400 flex items-start gap-2">
      <svg className="w-4 h-4 mt-0.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
        <circle cx="12" cy="12" r="10" />
        <path d="m15 9-6 6M9 9l6 6" />
      </svg>
      {children}
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5 mx-auto" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg className="w-4.5 h-4.5" viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function mapError(code: string): string {
  const map: Record<string, string> = {
    "auth/email-already-in-use":      "该邮箱已被注册",
    "auth/invalid-email":             "邮箱格式不正确",
    "auth/user-not-found":            "账号不存在",
    "auth/wrong-password":            "密码错误",
    "auth/invalid-credential":        "邮箱或密码不正确",
    "auth/weak-password":             "密码强度不够，请使用至少 6 位",
    "auth/too-many-requests":         "尝试次数过多，请稍后再试",
    "auth/invalid-phone-number":      "手机号格式不正确",
    "auth/invalid-verification-code": "验证码不正确",
    "auth/code-expired":              "验证码已过期，请重新获取",
    "auth/missing-phone-number":      "请输入手机号",
    "auth/quota-exceeded":            "短信额度已用完，请稍后再试",
    "auth/network-request-failed":    "网络错误，请检查网络连接",
  };
  return map[code] || `操作失败 (${code})`;
}
