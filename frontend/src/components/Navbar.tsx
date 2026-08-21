"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import { Zap, Activity, User, Users, LineChart, LogIn, LogOut } from "lucide-react";
import AuthModal from "./AuthModal";

export default function Navbar() {
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [authOpen, setAuthOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setUser(data?.session?.user || null);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user || null);
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  const navItems = [
    { label: "数据看板", href: "/dashboard", icon: Activity },
    { label: "跑者档案与目标", href: "/dashboard/profile", icon: User },
    { label: "Canova AI 教练", href: "/dashboard/coach", icon: Zap },
    { label: "深度分析", href: "/dashboard/analysis", icon: LineChart },
    { label: "跑团与排行榜", href: "/dashboard/team", icon: Users },
  ];

  return (
    <>
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#0a0a0a]/80 border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 font-black text-xl tracking-tight">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#FC4C02] to-orange-400 flex items-center justify-center text-white shadow-lg shadow-[#FC4C02]/20">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <span>RGM <span className="text-[#FC4C02] text-sm font-semibold ml-1">国内版</span></span>
          </Link>

          {/* Nav Links */}
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? "bg-white/10 text-white shadow-sm"
                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? "text-[#FC4C02]" : ""}`} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* User Auth Action */}
          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-400 hidden sm:inline">
                  {user.email || user.user_metadata?.display_name || "已登录"}
                </span>
                <button
                  onClick={() => supabase.auth.signOut()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-medium text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  退出
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAuthOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-bold hover:bg-orange-600 transition-all shadow-md shadow-[#FC4C02]/20"
              >
                <LogIn className="w-3.5 h-3.5" />
                登录 / 注册
              </button>
            )}
          </div>
        </div>
      </header>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
    </>
  );
}
