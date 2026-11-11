"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import apiClient from "@/lib/apiClient";
import {
  Zap,
  Activity,
  User,
  Users,
  LogIn,
  LogOut,
  Shield,
  BookOpen,
  ClipboardCheck,
  Sun,
  Moon,
  Bell,
  CheckCheck,
} from "lucide-react";
import AuthModal from "./AuthModal";
import CoachChatBox from "./CoachChatBox";

export default function Navbar() {
  const pathname = usePathname();
  const [user, setUser] = useState<any>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<"dark" | "light">("dark");
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  async function loadNotifications(uid: string) {
    if (!uid) return;
    try {
      const res = await apiClient.get(`/api/notifications?user_id=${encodeURIComponent(uid)}&limit=20`);
      const list = Array.isArray(res.data?.notifications) ? res.data.notifications : [];
      setNotifications(list);
      setUnreadCount(
        typeof res.data?.unread_count === "number"
          ? res.data.unread_count
          : list.filter((n: any) => !n.is_read).length
      );
    } catch {
      // Non-blocking notification fetch
    }
  }

  async function handleMarkNotifRead(notifId: string) {
    if (!user?.id || !notifId) return;
    try {
      await apiClient.post(`/api/notifications/${encodeURIComponent(notifId)}/read?user_id=${encodeURIComponent(user.id)}`);
      setNotifications((prev) => prev.map((n) => (n.id === notifId ? { ...n, is_read: 1 } : n)));
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {}
  }

  async function handleMarkAllNotifsRead() {
    if (!user?.id) return;
    try {
      await apiClient.post("/api/notifications/read-all", { user_id: user.id });
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: 1 })));
      setUnreadCount(0);
    } catch {}
  }
  const [isCoachOrOwner, setIsCoachOrOwner] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      const cached = localStorage.getItem("rgm_is_coach_or_owner");
      if (cached === "true") return true;
      try {
        const raw = localStorage.getItem("rgm_auth_session");
        if (raw) {
          const sess = JSON.parse(raw);
          const u = sess?.user;
          if (u?.is_coach_or_owner || u?.is_admin) {
            return true;
          }
        }
      } catch {}
    }
    return false;
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("rgm_theme_mode");
      const mode = saved === "light" ? "light" : "dark";
      setThemeMode(mode);
      document.documentElement.classList.toggle("theme-light", mode === "light");
    }
  }, []);

  function handleToggleTheme() {
    const next = themeMode === "dark" ? "light" : "dark";
    setThemeMode(next);
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_theme_mode", next);
      document.documentElement.classList.toggle("theme-light", next === "light");
    }
  }

  const checkRole = async (u: any) => {
    if (!u || !u.id) {
      setIsCoachOrOwner(false);
      if (typeof window !== "undefined") {
        localStorage.removeItem("rgm_is_coach_or_owner");
      }
      return;
    }
    if (
      u.is_coach_or_owner ||
      u.is_admin ||
      u.id === "admin" ||
      u.id === "super_admin"
    ) {
      setIsCoachOrOwner(true);
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_is_coach_or_owner", "true");
      }
      return;
    }
    try {
      const res = await apiClient.get(`/api/team/my-clubs/${encodeURIComponent(u.id)}`);
      const clubs = res.data?.clubs || [];
      const hasRole = Boolean(
        res.data?.is_coach_or_owner ||
          clubs.some(
            (c: any) => c.role === "owner" || c.role === "coach" || c.role === "admin"
          )
      );
      setIsCoachOrOwner(hasRole);
      if (typeof window !== "undefined") {
        localStorage.setItem("rgm_is_coach_or_owner", hasRole ? "true" : "false");
      }
    } catch {
      // Keep cached value on network error to prevent tab disappearing
    }
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const u = data?.session?.user || null;
      setUser(u);
      checkRole(u);
      if (u?.id) loadNotifications(u.id);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const u = session?.user || null;
      setUser(u);
      checkRole(u);
      if (u?.id) {
        loadNotifications(u.id);
      } else {
        setNotifications([]);
        setUnreadCount(0);
      }
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  const isSuperAdmin = Boolean(
    user &&
      (user.id === "admin" ||
        user.id === "super_admin" ||
        user.is_admin)
  );

  // 与小程序底部 5 大 Tab 完全对齐：首页 · 训练（含课表/诊断/身体数据） · 跑团 · 教练 · 我的
  const navItems = [
    { label: "首页", href: "/dashboard", icon: Activity, matchPaths: ["/dashboard"] },
    { label: "训练", href: "/dashboard/coach", icon: Zap, matchPaths: ["/dashboard/coach", "/dashboard/analysis"] },
    { label: "跑团", href: "/dashboard/team", icon: Users, matchPaths: ["/dashboard/team"] },
    ...(isCoachOrOwner
      ? [{ label: "教练", href: "/dashboard/team-coach", icon: ClipboardCheck, matchPaths: ["/dashboard/team-coach"] }]
      : []),
    { label: "我的", href: "/dashboard/profile", icon: User, matchPaths: ["/dashboard/profile"] },
  ];

  return (
    <>
      <header className="sticky top-0 z-50 backdrop-blur-md bg-[#121216] border-b border-white/10 transition-colors duration-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-2">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-2.5 font-black text-xl tracking-tight whitespace-nowrap shrink-0">
            <img
              src="/logo.png"
              alt="万跑跑团助手 Logo"
              width={36}
              height={36}
              className="w-9 h-9 rounded-lg object-contain bg-white shadow-lg shadow-[#FC4C02]/20 shrink-0"
            />
            <span className="text-white">
              万跑跑团助手{" "}
              <span className="text-[#FC4C02] text-xs font-bold ml-1 px-2 py-0.5 rounded-full bg-[#FC4C02]/10 border border-[#FC4C02]/30">
                Web 工作台
              </span>
            </span>
          </Link>

          {/* Desktop Primary 5-Tab Nav (Aligned with MiniApp) */}
          <nav className="hidden md:flex items-center gap-1.5 bg-white/[0.03] border border-white/[0.07] p-1 rounded-2xl overflow-x-auto no-scrollbar">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = item.matchPaths.includes(pathname);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs lg:text-sm font-bold whitespace-nowrap shrink-0 transition-all ${
                    isActive
                      ? "bg-[#FC4C02] text-white shadow-md shadow-[#FC4C02]/25"
                      : "text-zinc-400 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-white" : ""}`} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Right Utility & User Auth Action */}
          <div className="flex items-center gap-2 shrink-0">
            {/* Quick Theme Mode Toggle (Light / Dark) */}
            <button
              onClick={handleToggleTheme}
              title={themeMode === "dark" ? "切换为明亮页面模式" : "切换为深色页面模式"}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-bold transition cursor-pointer ${
                themeMode === "light"
                  ? "bg-amber-500/15 border-amber-500/40 text-amber-600 hover:bg-amber-500/25"
                  : "bg-white/[0.03] border-white/10 text-zinc-300 hover:text-white hover:bg-white/10"
              }`}
            >
              {themeMode === "dark" ? (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span className="hidden sm:inline">明亮</span>
                </>
              ) : (
                <>
                  <Moon className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
                  <span className="hidden sm:inline">深色</span>
                </>
              )}
            </button>

            <Link
              href="/dashboard/manual"
              title="帮助与常见问题"
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition ${
                pathname === "/dashboard/manual"
                  ? "bg-white/10 border-white/20 text-white"
                  : "bg-white/[0.03] border-white/10 text-zinc-400 hover:text-white hover:bg-white/10"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 shrink-0" />
              <span className="hidden sm:inline">帮助</span>
            </Link>

            {isSuperAdmin && (
              <Link
                href="/dashboard/admin"
                title="超级管理后台"
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition ${
                  pathname === "/dashboard/admin"
                    ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                    : "bg-white/[0.03] border-white/10 text-zinc-400 hover:text-amber-300 hover:bg-amber-500/10"
                }`}
              >
                <Shield className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden lg:inline">超管</span>
              </Link>
            )}

            {user ? (
              <div className="flex items-center gap-2 relative">
                <button
                  type="button"
                  onClick={() => {
                    const next = !notifOpen;
                    setNotifOpen(next);
                    if (next && user?.id) loadNotifications(user.id);
                  }}
                  title="站内系统与教练通知"
                  className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.03] border border-white/10 text-zinc-300 hover:text-white hover:bg-white/10 transition cursor-pointer"
                >
                  <Bell className="w-3.5 h-3.5" />
                  {unreadCount > 0 && (
                    <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-[#FC4C02] text-white text-[10px] font-black flex items-center justify-center">
                      {unreadCount > 99 ? "99+" : unreadCount}
                    </span>
                  )}
                </button>

                {notifOpen && (
                  <div className="absolute right-0 top-11 w-80 sm:w-96 max-h-[70vh] bg-[#16161b] border border-white/15 rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col">
                    <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between">
                      <span className="text-xs font-black text-white">
                        消息中心 {unreadCount > 0 ? `(${unreadCount} 条未读)` : ""}
                      </span>
                      <div className="flex items-center gap-2">
                        {unreadCount > 0 && (
                          <button
                            type="button"
                            onClick={handleMarkAllNotifsRead}
                            className="text-[11px] text-emerald-400 hover:text-emerald-300 font-bold flex items-center gap-1 cursor-pointer"
                          >
                            <CheckCheck className="w-3 h-3" />
                            全部已读
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setNotifOpen(false)}
                          className="text-xs text-zinc-400 hover:text-white cursor-pointer"
                        >
                          关闭
                        </button>
                      </div>
                    </div>
                    <div className="overflow-y-auto divide-y divide-white/5 max-h-80">
                      {notifications.length === 0 ? (
                        <div className="py-10 text-center text-xs text-zinc-500">
                          暂无新消息 · 教练点评与课表推送将在此显示
                        </div>
                      ) : (
                        notifications.map((n: any) => (
                          <div
                            key={n.id}
                            onClick={() => {
                              if (!n.is_read) handleMarkNotifRead(n.id);
                            }}
                            className={`px-4 py-3 transition cursor-pointer hover:bg-white/[0.04] ${
                              !n.is_read ? "bg-[#FC4C02]/[0.06]" : ""
                            }`}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="text-xs font-bold text-white flex items-center gap-1.5">
                                {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-[#FC4C02] shrink-0" />}
                                {n.title || "系统通知"}
                              </span>
                              <span className="text-[10px] text-zinc-500 shrink-0">
                                {String(n.created_at || "").slice(5, 16).replace("T", " ")}
                              </span>
                            </div>
                            <p className="text-[11px] text-zinc-300 mt-1 leading-relaxed line-clamp-3">
                              {n.content}
                            </p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                <span className="text-xs text-zinc-400 hidden xl:inline truncate max-w-[140px]">
                  {user.display_name || user.user_metadata?.display_name || user.email || "已登录"}
                </span>
                <button
                  onClick={() => supabase.auth.signOut()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-medium whitespace-nowrap text-zinc-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
                >
                  <LogOut className="w-3.5 h-3.5 shrink-0" />
                  退出
                </button>
              </div>
            ) : (
              <button
                onClick={() => setAuthOpen(true)}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] text-white text-xs font-bold whitespace-nowrap hover:bg-orange-600 transition-all shadow-md shadow-[#FC4C02]/20"
              >
                <LogIn className="w-3.5 h-3.5 shrink-0" />
                登录 / 注册
              </button>
            )}
          </div>
        </div>

        {/* Mobile / Narrow Window Nav Links */}
        <nav className="flex md:hidden items-center justify-around gap-1 px-3 pb-2.5 overflow-x-auto no-scrollbar border-t border-white/5 pt-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.matchPaths.includes(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap shrink-0 transition-all ${
                  isActive
                    ? "bg-[#FC4C02] text-white shadow-sm"
                    : "text-zinc-400 hover:text-white hover:bg-white/5"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-white" : ""}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
      {user?.id && pathname?.startsWith("/dashboard") && <CoachChatBox uid={user.id} />}
    </>
  );
}
