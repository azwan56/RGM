"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import Navbar from "@/components/Navbar";
import AuthModal from "@/components/AuthModal";
import { Zap, Activity, ShieldCheck, Trophy, Sparkles, Smartphone } from "lucide-react";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data?.session?.user || null);
      setAuthLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  const isLoggedIn = !!user;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative">
      <Navbar />

      {/* Aesthetic Background Glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[45%] h-[45%] rounded-full bg-[#FC4C02]/15 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/10 blur-[160px] pointer-events-none" />

      <main className="max-w-7xl mx-auto px-4 md:px-6 pt-20 pb-24 text-center flex flex-col items-center justify-center relative z-10">
        <div className="mb-6 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-semibold text-zinc-300 backdrop-blur-md">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          阿里云全栈直连 · 纯净 Garmin 佳明生态
        </div>

        <h1 className="text-4xl sm:text-6xl md:text-8xl font-black mb-6 tracking-tight">
          记录. <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FC4C02] to-orange-400">竞争.</span> 进化.
        </h1>

        <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mx-auto mb-10 font-light leading-relaxed">
          专为国内跑者与跑团打造的一站式数据管理平台。
          直连佳明手表自动同步、Canova AI 教练专项化指导、微信小程序随时随地掌握进度。
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          {authLoading ? (
            <div className="w-48 h-12 bg-white/5 rounded-2xl animate-pulse" />
          ) : isLoggedIn ? (
            <button
              onClick={() => router.push("/dashboard")}
              className="px-8 py-3.5 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-2xl transition-all hover:shadow-lg hover:shadow-[#FC4C02]/30 flex items-center justify-center gap-2 text-sm"
            >
              <Activity className="w-4 h-4" />
              进入数据看板 Dashboard
            </button>
          ) : (
            <>
              <button
                onClick={() => setModalOpen(true)}
                className="px-8 py-3.5 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-2xl transition-all hover:shadow-lg hover:shadow-[#FC4C02]/30 flex items-center justify-center gap-2 text-sm"
              >
                立即免费使用
              </button>
              <button
                onClick={() => setModalOpen(true)}
                className="px-6 py-3.5 bg-white/5 border border-white/10 hover:bg-white/10 text-white font-semibold rounded-2xl transition-all flex items-center justify-center gap-2 text-sm"
              >
                <Smartphone className="w-4 h-4 text-[#FC4C02]" />
                微信小程序扫码
              </button>
            </>
          )}
        </div>

        {/* Feature Cards Grid */}
        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto w-full text-left">
          <div className="bg-white/5 border border-white/10 p-6 sm:p-8 rounded-3xl backdrop-blur-sm hover:border-[#FC4C02]/30 transition-all">
            <div className="w-12 h-12 rounded-2xl bg-[#FC4C02]/10 border border-[#FC4C02]/20 flex items-center justify-center text-[#FC4C02] mb-5">
              <Activity className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold mb-2 text-white">佳明双区直连</h3>
            <p className="text-zinc-400 text-xs sm:text-sm leading-relaxed">
              支持 Garmin 中国版 (`garmin.cn`) 与国际版账号一键连接，自动拉取配速、步频、心率区间与 HRV/睡眠体能数据。
            </p>
          </div>

          <div className="bg-white/5 border border-white/10 p-6 sm:p-8 rounded-3xl backdrop-blur-sm hover:border-purple-500/30 transition-all">
            <div className="w-12 h-12 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-5">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold mb-2 text-white">Canova AI 教练</h3>
            <p className="text-zinc-400 text-xs sm:text-sm leading-relaxed">
              基于世界顶级马拉松教练 Renato Canova 的专项性哲学，接入通义千问/DeepSeek，评估体能差距与关键课设计。
            </p>
          </div>

          <div className="bg-white/5 border border-white/10 p-6 sm:p-8 rounded-3xl backdrop-blur-sm hover:border-amber-500/30 transition-all">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-5">
              <Trophy className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold mb-2 text-white">跑团排行榜与小程序</h3>
            <p className="text-zinc-400 text-xs sm:text-sm leading-relaxed">
              6位邀请码快速组建战队，按目标完成率竞跑；微信小程序端随时随地滑块调节目标，战报一键分享朋友圈。
            </p>
          </div>
        </div>
      </main>

      <AuthModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
