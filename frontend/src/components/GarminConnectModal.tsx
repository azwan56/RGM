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
}

export default function GarminConnectModal({ open, isOpen, onClose, uid, onSuccess }: GarminModalProps) {
  const isShown = open ?? isOpen ?? false;
  const [domain, setDomain] = useState<"garmin.cn" | "garmin.com">("garmin.cn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!isShown) return null;

  async function handleBind(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    try {
      await apiClient.post("/api/auth/garmin/bind", {
        uid,
        email,
        password,
        domain,
      });
      alert(`佳明账号 (${domain}) 绑定成功！已开始自动同步最近运动数据。`);
      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || "绑定失败，请检查账号密码与区域。");
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

        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-[#FC4C02]/10 border border-[#FC4C02]/30 flex items-center justify-center text-[#FC4C02]">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">连接 Garmin 佳明账号</h2>
            <p className="text-xs text-zinc-400">直连官方服务器同步跑步与健康数据</p>
          </div>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleBind} className="space-y-4">
          {/* Domain Picker */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5 flex items-center gap-1">
              <Globe className="w-3.5 h-3.5" /> 佳明账号所属区域
            </label>
            <div className="grid grid-cols-2 gap-2 bg-white/5 p-1 rounded-xl border border-white/5">
              <button
                type="button"
                onClick={() => setDomain("garmin.cn")}
                className={`py-2 rounded-lg text-xs font-bold transition-all ${
                  domain === "garmin.cn" ? "bg-[#FC4C02] text-white shadow" : "text-zinc-400 hover:text-white"
                }`}
              >
                中国版 (garmin.cn)
              </button>
              <button
                type="button"
                onClick={() => setDomain("garmin.com")}
                className={`py-2 rounded-lg text-xs font-bold transition-all ${
                  domain === "garmin.com" ? "bg-[#FC4C02] text-white shadow" : "text-zinc-400 hover:text-white"
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
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02] transition-all"
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
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white focus:outline-none focus:border-[#FC4C02] transition-all"
            />
          </div>

          <div className="flex items-start gap-2 p-3 bg-white/5 rounded-xl border border-white/5 text-[11px] text-zinc-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <span>您的凭据经过 AES-256-GCM 安全加密，仅在后端用于从 Garmin 官方获取运动记录，绝不泄露给任何第三方。</span>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-[#FC4C02]/20 hover:opacity-90 transition-all disabled:opacity-50"
          >
            {loading ? "正在验证并连接..." : "确认绑定并即时同步"}
          </button>
        </form>
      </div>
    </div>
  );
}
