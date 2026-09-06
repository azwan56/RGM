"use client";

import { useState } from "react";
import apiClient from "@/lib/apiClient";
import { X, ShieldCheck, Activity, Globe } from "lucide-react";

interface GarminModalProps {
  open?: boolean;
  isOpen?: boolean;
  onClose: () => void;
  uid: string;
  onSuccess: () => void;
  initialBrand?: "garmin" | "coros";
}

export default function GarminConnectModal({ 
  open, 
  isOpen, 
  onClose, 
  uid, 
  onSuccess,
  initialBrand = "garmin" 
}: GarminModalProps) {
  const isShown = open ?? isOpen ?? false;
  const [brand, setBrand] = useState<"garmin" | "coros">(initialBrand);
  
  // Garmin states
  const [domain, setDomain] = useState<"garmin.cn" | "garmin.com">("garmin.cn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [needsMfa, setNeedsMfa] = useState(false);
  const [mfaCode, setMfaCode] = useState("");

  // COROS states
  const [corosDomain, setCorosDomain] = useState<"teamcnapi.coros.com" | "teamapi.coros.com">("teamcnapi.coros.com");
  const [corosAccount, setCorosAccount] = useState("");
  const [corosPassword, setCorosPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!isShown) return null;

  async function handleBind(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      if (brand === "garmin") {
        const payload: any = {
          uid,
          email,
          password,
          domain,
        };
        if (needsMfa && mfaCode.trim()) {
          payload.mfa_code = mfaCode.trim();
        }

        const res = await apiClient.post("/api/auth/garmin/bind", payload);

        if (res.data?.needs_mfa) {
          setNeedsMfa(true);
          setLoading(false);
          return;
        }

        alert(`佳明账号 (${domain}) 绑定成功！已开始自动同步最近运动数据。`);
        setNeedsMfa(false);
        setMfaCode("");
      } else {
        const payload = {
          uid,
          account: corosAccount.trim(),
          password: corosPassword.trim(),
          domain: corosDomain,
        };

        await apiClient.post("/api/auth/coros/bind", payload);
        alert(`高驰账号 (${corosDomain.includes("cn") ? "中国区" : "国际区"}) 绑定成功！已开始自动同步最近运动数据。`);
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "绑定失败，请检查账号密码与区域设置。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="relative w-full max-w-md bg-[#121214] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 flex items-center justify-center text-[#FC4C02]">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">连接运动手表数据</h2>
            <p className="text-xs text-zinc-400">直连官方服务器自动同步跑步与健康数据</p>
          </div>
        </div>

        {/* Brand Switcher Tabs */}
        <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-2xl border border-white/10 mb-5">
          <button
            type="button"
            onClick={() => { setBrand("garmin"); setErrorMsg(""); }}
            className={`py-2 rounded-xl text-xs font-bold transition-all ${
              brand === "garmin" ? "bg-[#0A84FF] text-white shadow" : "text-zinc-400 hover:text-white"
            }`}
          >
            Garmin 佳明
          </button>
          <button
            type="button"
            onClick={() => { setBrand("coros"); setErrorMsg(""); }}
            className={`py-2 rounded-xl text-xs font-bold transition-all ${
              brand === "coros" ? "bg-[#FC4C02] text-white shadow" : "text-zinc-400 hover:text-white"
            }`}
          >
            COROS 高驰
          </button>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleBind} className="space-y-4">
          {brand === "garmin" ? (
            needsMfa ? (
              <div className="space-y-4">
                <div className="p-3.5 bg-amber-500/10 border border-amber-500/30 rounded-2xl">
                  <span className="text-amber-400 font-bold text-xs block mb-1">🔒 佳明官方双重安全验证</span>
                  <span className="text-xs text-zinc-300 block leading-relaxed">
                    佳明官方已向您的注册邮箱或手机发送了 6 位安全验证码，请输入以完成账号绑定：
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">6 位安全验证码</label>
                  <input
                    type="text"
                    required
                    maxLength={6}
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                    placeholder="例如: 123456"
                    className="w-full px-4 py-2.5 bg-white/5 border border-amber-500/50 rounded-xl text-center text-lg tracking-widest font-mono text-white focus:outline-none focus:border-amber-400 transition-all"
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-amber-500 to-orange-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-amber-500/20 hover:opacity-90 transition-all disabled:opacity-50"
                >
                  {loading ? "正在验证..." : "提交验证码并完成绑定"}
                </button>

                <button
                  type="button"
                  onClick={() => setNeedsMfa(false)}
                  className="w-full text-center text-xs text-zinc-400 hover:text-white pt-1 transition-colors"
                >
                  返回修改账号密码
                </button>
              </div>
            ) : (
              <>
                {/* Garmin Domain Picker */}
                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5 flex items-center gap-1">
                    <Globe className="w-3.5 h-3.5" /> 佳明账号所属区域
                  </label>
                  <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-xl border border-white/5">
                    <button
                      type="button"
                      onClick={() => setDomain("garmin.cn")}
                      className={`py-2 rounded-lg text-xs font-bold transition-all ${
                        domain === "garmin.cn" ? "bg-[#0A84FF] text-white shadow" : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      中国版 (garmin.cn)
                    </button>
                    <button
                      type="button"
                      onClick={() => setDomain("garmin.com")}
                      className={`py-2 rounded-lg text-xs font-bold transition-all ${
                        domain === "garmin.com" ? "bg-[#0A84FF] text-white shadow" : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      国际版 (garmin.com)
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">佳明 Connect 账号 / 邮箱</label>
                  <input
                    type="text"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="例如: runner@example.com"
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#0A84FF] transition-all"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-zinc-400 mb-1.5">佳明 Connect 密码</label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="输入佳明密码"
                    className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#0A84FF] transition-all"
                  />
                </div>

                <div className="flex items-start gap-2 p-3 bg-white/5 rounded-xl border border-white/5 text-[11px] text-zinc-400">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>您的凭据经过 AES-256-GCM 安全加密，仅在后端用于从 Garmin 官方获取运动记录，绝不泄露给任何第三方。</span>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-gradient-to-r from-[#0A84FF] to-blue-600 text-white font-bold rounded-xl text-sm shadow-lg shadow-blue-500/20 hover:opacity-90 transition-all disabled:opacity-50"
                >
                  {loading ? "正在验证并连接..." : "确认绑定佳明并即时同步"}
                </button>
              </>
            )
          ) : (
            /* COROS TAB */
            <>
              {/* COROS Domain Picker */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5 flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5" /> 高驰账号所属区域
                </label>
                <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-xl border border-white/5">
                  <button
                    type="button"
                    onClick={() => setCorosDomain("teamcnapi.coros.com")}
                    className={`py-2 rounded-lg text-xs font-bold transition-all ${
                      corosDomain === "teamcnapi.coros.com" ? "bg-[#FC4C02] text-white shadow" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    中国区 (teamcnapi)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCorosDomain("teamapi.coros.com")}
                    className={`py-2 rounded-lg text-xs font-bold transition-all ${
                      corosDomain === "teamapi.coros.com" ? "bg-[#FC4C02] text-white shadow" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    国际区 (teamapi)
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">高驰注册账号（手机号或邮箱）</label>
                <input
                  type="text"
                  required
                  value={corosAccount}
                  onChange={(e) => setCorosAccount(e.target.value)}
                  placeholder="例如: 13800000000 或 runner@example.com"
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02] transition-all"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1.5">高驰登录密码</label>
                <input
                  type="password"
                  required
                  value={corosPassword}
                  onChange={(e) => setCorosPassword(e.target.value)}
                  placeholder="输入高驰登录密码"
                  className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02] transition-all"
                />
              </div>

              <div className="flex items-start gap-2 p-3 bg-white/5 rounded-xl border border-white/5 text-[11px] text-zinc-400">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>您的凭据经过 AES-256-GCM 安全加密，仅在后端用于从 COROS Training Hub 获取运动记录，绝不泄露给任何第三方。</span>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-[#FC4C02]/20 hover:opacity-90 transition-all disabled:opacity-50"
              >
                {loading ? "正在验证并连接..." : "确认绑定高驰并即时同步"}
              </button>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
