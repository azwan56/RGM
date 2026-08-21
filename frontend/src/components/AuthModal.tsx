"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { X, Mail, Lock, Smartphone, QrCode } from "lucide-react";

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
}

export default function AuthModal({ open, onClose }: AuthModalProps) {
  const [tab, setTab] = useState<"email" | "phone">("email");
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  if (!open) return null;

  async function handleEmailAuth(e: React.FormEvent) {
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
        onClose();
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        onClose();
      }
    } catch (err: any) {
      setErrorMsg(err.message || "认证失败，请检查输入");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="relative w-full max-w-md bg-[#121214] border border-white/10 rounded-3xl p-6 sm:p-8 shadow-2xl">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-6 right-6 p-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/5 transition-all"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Title */}
        <div className="mb-6 text-center">
          <h2 className="text-2xl font-black text-white">
            {isSignUp ? "加入 RGM 跑团" : "登录 RGM 跑团"}
          </h2>
          <p className="text-xs text-zinc-400 mt-1.5">
            连接 Garmin 佳明数据，开启专属 AI 马拉松训练
          </p>
        </div>

        {/* Auth Mode Tabs */}
        <div className="flex bg-white/5 p-1 rounded-2xl mb-6 border border-white/5">
          <button
            onClick={() => setTab("email")}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              tab === "email" ? "bg-[#FC4C02] text-white shadow-md" : "text-zinc-400 hover:text-white"
            }`}
          >
            <Mail className="w-3.5 h-3.5" />
            邮箱登录
          </button>
          <button
            onClick={() => setTab("phone")}
            className={`flex-1 py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              tab === "phone" ? "bg-[#FC4C02] text-white shadow-md" : "text-zinc-400 hover:text-white"
            }`}
          >
            <Smartphone className="w-3.5 h-3.5" />
            微信小程序免密
          </button>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs">
            {errorMsg}
          </div>
        )}

        {tab === "email" ? (
          <form onSubmit={handleEmailAuth} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">邮箱地址</label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="runner@example.com"
                  className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02] transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">登录密码</label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-3 w-4 h-4 text-zinc-500" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 6 位字符"
                  className="w-full pl-10 pr-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-[#FC4C02] transition-all"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-xl text-sm shadow-lg shadow-[#FC4C02]/20 hover:opacity-90 transition-all disabled:opacity-50"
            >
              {loading ? "处理中..." : isSignUp ? "立即注册" : "进入平台"}
            </button>

            <div className="text-center pt-2">
              <button
                type="button"
                onClick={() => setIsSignUp(!isSignUp)}
                className="text-xs text-zinc-400 hover:text-white transition-colors"
              >
                {isSignUp ? "已有账号？直接登录" : "还没有账号？点击免费注册"}
              </button>
            </div>
          </form>
        ) : (
          <div className="text-center py-6">
            <div className="w-36 h-36 mx-auto bg-white/5 border border-white/10 rounded-2xl flex items-center justify-center mb-4">
              <QrCode className="w-20 h-20 text-[#FC4C02]" />
            </div>
            <p className="text-xs text-zinc-300 font-medium">使用微信扫码打开 RGM 小程序</p>
            <p className="text-[11px] text-zinc-500 mt-1">支持微信一键登录与手表数据秒级同步</p>
          </div>
        )}
      </div>
    </div>
  );
}
