"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Navbar from "@/components/Navbar";
import { Mail, Lock, Zap, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data?.session?.user) {
        router.push("/dashboard");
      }
    });
  }, [router]);

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
        router.push("/dashboard");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (error) throw error;
        router.push("/dashboard");
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
        <div className="w-full max-w-md bg-[#121215] border border-white/10 rounded-3xl p-8 shadow-2xl space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-[#FC4C02] to-orange-400 flex items-center justify-center text-white mx-auto shadow-lg shadow-[#FC4C02]/20">
              <Zap className="w-6 h-6 fill-current" />
            </div>
            <h1 className="text-2xl font-black text-white">
              {isSignUp ? "创建跑者账号" : "登录 RGM 国内版"}
            </h1>
            <p className="text-xs text-zinc-400">
              直连 Garmin 佳明 / 高驰手表 · Canova教练专项化指导
            </p>
          </div>

          {errorMsg && (
            <div className="p-3 bg-red-950/40 border border-red-500/30 rounded-xl text-xs text-red-200">
              {errorMsg}
            </div>
          )}

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <label className="text-xs text-zinc-400 block mb-1.5">邮箱地址</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-zinc-500 absolute left-3.5 top-3" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="runner@example.com"
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
                  placeholder="••••••••"
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

          <div className="pt-4 border-t border-white/5 flex items-center justify-between text-xs text-zinc-400">
            <button
              type="button"
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-[#FC4C02] hover:underline"
            >
              {isSignUp ? "已有账号？直接登录" : "没有账号？免费注册"}
            </button>

            <Link href="/" className="hover:text-white transition-colors">
              返回官网首页
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
