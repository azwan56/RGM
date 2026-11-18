"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect, useCallback } from "react";
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
  ShieldCheck,
  BookOpen,
  ClipboardCheck,
  Sun,
  Moon,
  Bell,
  CheckCheck,
  Search,
  Compass,
  Crown,
  Target,
  Sparkles,
  BarChart3,
  Wrench,
  Watch,
} from "lucide-react";
import AuthModal from "./AuthModal";
import CoachChatBox from "./CoachChatBox";
import CommandPaletteModal, { dispatchRgmNavIntent } from "./web3/CommandPaletteModal";

type RolePerspective = "runner" | "leader" | "admin";

function resolvePageMeta(pathname: string | null, searchStr: string): { title: string; subtitle: string } {
  const sp = new URLSearchParams(searchStr || "");
  const tab = sp.get("tab") || "";
  const mode = sp.get("mode") || "";
  const orgAction = sp.get("org_action") || "";

  if (pathname === "/dashboard/coach") {
    if (tab === "report") {
      return { title: "Canova 战略诊断报告", subtitle: "多赛事周期路线图 · A/B/C 优先级冲突排查 · 专项配速" };
    }
    return { title: "Canova 科学训练中心", subtitle: "W1–W8 周期化动态课表 · 双栏 AI 教练实时调课" };
  }
  if (pathname === "/dashboard/analysis") {
    return { title: "运动生理与轨迹复盘", subtitle: "有效 VDOT · Taper 减量推演 · 官兔潜能评估 · 4K 战报" };
  }
  if (pathname === "/dashboard/team-coach" || (pathname === "/dashboard/team" && tab === "coach")) {
    if (mode === "batch-critique") {
      return { title: "教练 5 秒连续批阅三栏舱", subtitle: "异常置顶队列 · AI 遥测对照 · 快捷词条连续发送" };
    }
    return { title: "教练工作台与选兔雷达", subtitle: "红黄绿灰体能信号灯 · 跨视角审课 · 批量派发" };
  }
  if (pathname === "/dashboard/team") {
    if (orgAction === "audit") {
      return { title: "大群 14 天实名准入核验", subtitle: "AES-256 脱敏花名册审计 · 转正与解冻核准" };
    }
    if (tab === "president") {
      return { title: "团长运营驾驶舱", subtitle: "全团达标率圆环 · 激活漏斗 · 邀请码与成员精细管理" };
    }
    if (tab === "events") {
      return { title: "周末约跑与配速列车", subtitle: "公园门岗锚点 · 300–430 列车编组 · 赛后 92% 战报" };
    }
    return { title: "跑团社交主页与大群生态", subtitle: "完成率/跑量双模榜 · 教练精评蓝框 · 师徒结对" };
  }
  if (pathname === "/dashboard/profile") {
    if (tab === "device") {
      return { title: "运动手表双区直连设置", subtitle: "Garmin 中国区 (garmin.cn) / 国际区 · COROS 高驰同步" };
    }
    if (tab === "training") {
      return { title: "赛事档案与跑量规划", subtitle: "A/B/C 赛事计划 · AI 情报检索 · 手表成绩匹配" };
    }
    return { title: "档案、绑表与 4 级隐私中心", subtitle: "三栏一屏重构 · AES-256 加密底账 · 14 天大群准入" };
  }
  if (pathname === "/dashboard/admin") {
    if (tab === "analytics") {
      return { title: "平台超管 · 增长漏斗与遥测", subtitle: "小程序 + Web 双端 DAU · 激活转化漏斗 · 单跑者钻取" };
    }
    if (tab === "support") {
      return { title: "平台超管 · 设备与 AI 运维", subtitle: "佳明双区/高驰健康监控 · Canova AI 队列 · 工单秒修" };
    }
    if (tab === "unaffiliated") {
      return { title: "平台超管 · 自由跑者待激活池", subtitle: "已绑表未入团跑友识别 · 一键推送周边跑团邀请" };
    }
    if (tab === "clubs") {
      return { title: "平台超管 · 跑团全生命周期治理", subtitle: "新建/编辑跑团 · 指派团长 · 暂停锁定与防误删确认" };
    }
    return { title: "平台超管控制台", subtitle: "全站大群与分团架构树 · 实名核验 · 运维与遥测总控" };
  }
  if (pathname === "/dashboard/manual") {
    return { title: "新用户操作手册与 FAQ", subtitle: "佳明双区切换 · 14 天实名准入与常见排障说明" };
  }
  return { title: "跑者全息工作台", subtitle: "今日 Canova 处方 · 三维跑量圆环 · 30 天负荷与团榜" };
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<"dark" | "light">("dark");
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasManagedOrg, setHasManagedOrg] = useState(false);
  const [watchStatusLabel, setWatchStatusLabel] = useState("未绑定手表");
  const [watchConnected, setWatchConnected] = useState(false);
  const [profileDisplayName, setProfileDisplayName] = useState("");
  const [searchStr, setSearchStr] = useState("");

  const [rolePerspective, setRolePerspective] = useState<RolePerspective>("runner");

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

  const loadNotifications = useCallback(async (uid: string) => {
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
  }, []);

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

  const applyThemeMode = useCallback((mode: "dark" | "light") => {
    setThemeMode(mode);
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_theme_mode", mode);
      document.documentElement.classList.toggle("theme-light", mode === "light");
    }
  }, []);

  const handleToggleTheme = useCallback(() => {
    const next: "dark" | "light" = themeMode === "dark" ? "light" : "dark";
    applyThemeMode(next);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("rgm-theme-change", { detail: next }));
    }
  }, [themeMode, applyThemeMode]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const saved = localStorage.getItem("rgm_theme_mode");
    applyThemeMode(saved === "light" ? "light" : "dark");

    const onThemeSync = (e: Event) => {
      const next = (e as CustomEvent).detail;
      if (next === "dark" || next === "light") {
        applyThemeMode(next);
      }
    };
    window.addEventListener("rgm-theme-change", onThemeSync);
    return () => window.removeEventListener("rgm-theme-change", onThemeSync);
  }, [applyThemeMode]);

  // Global Cmd+K / Ctrl+K shortcut for Command Palette
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  // Track URL query string & sync active role perspective contextually
  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncFromUrl = (customHref?: string) => {
      const q = customHref && customHref.includes("?")
        ? `?${customHref.split("?")[1]}`
        : window.location.search;
      setSearchStr(q);
      const sp = new URLSearchParams(q);
      const tab = sp.get("tab") || "";
      const mode = sp.get("mode") || "";
      const orgAct = sp.get("org_action") || "";

      if (pathname === "/dashboard/admin" || orgAct === "audit") {
        setRolePerspective("admin");
        localStorage.setItem("rgm_role_perspective", "admin");
      } else if (
        pathname === "/dashboard/team-coach" ||
        (pathname === "/dashboard/team" && (tab === "president" || tab === "coach" || mode === "batch-critique"))
      ) {
        setRolePerspective("leader");
        localStorage.setItem("rgm_role_perspective", "leader");
      } else {
        const savedRole = localStorage.getItem("rgm_role_perspective") as RolePerspective | null;
        if (savedRole === "runner" || savedRole === "leader" || savedRole === "admin") {
          setRolePerspective(savedRole);
        }
      }
    };

    syncFromUrl();
    const onPop = () => syncFromUrl();
    const onNavIntent = (e: Event) => {
      const href = (e as CustomEvent)?.detail?.href;
      syncFromUrl(typeof href === "string" ? href : undefined);
    };
    window.addEventListener("popstate", onPop);
    window.addEventListener("rgm-nav-intent", onNavIntent);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.removeEventListener("rgm-nav-intent", onNavIntent);
    };
  }, [pathname]);

  const checkRole = useCallback(async (u: any) => {
    if (!u || !u.id) {
      setIsCoachOrOwner(false);
      setHasManagedOrg(false);
      setWatchConnected(false);
      setWatchStatusLabel("未绑定手表");
      if (typeof window !== "undefined") {
        localStorage.removeItem("rgm_is_coach_or_owner");
      }
      return;
    }

    const gConn = Boolean(u.garmin_connected);
    const cConn = Boolean(u.coros_connected);
    if (gConn || cConn) {
      setWatchConnected(true);
      setWatchStatusLabel(gConn && cConn ? "Garmin + COROS 在线" : gConn ? "Garmin 直连在线" : "COROS 直连在线");
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
    } else {
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
    }

    // Non-blocking org manager & watch status enrichment
    apiClient
      .get(`/api/org/my-orgs/${encodeURIComponent(u.id)}`)
      .then((res) => {
        const orgs = res.data?.organizations || [];
        const managed = orgs.some(
          (o: any) => o.is_organizer || o.role === "owner" || o.role === "admin" || o.owner_id === u.id
        );
        setHasManagedOrg(managed);
      })
      .catch(() => {});

    apiClient
      .get(`/api/profile/${encodeURIComponent(u.id)}`)
      .then((res) => {
        const p = res.data?.profile || res.data || {};
        if (p.display_name) setProfileDisplayName(p.display_name);
        const hasGarmin = Boolean(p.garmin_connected || u.garmin_connected);
        const hasCoros = Boolean(p.coros_connected || u.coros_connected);
        setWatchConnected(hasGarmin || hasCoros);
        if (hasGarmin && hasCoros) {
          setWatchStatusLabel("Garmin + COROS 在线");
        } else if (hasGarmin) {
          setWatchStatusLabel(p.garmin_domain === "garmin.com" ? "Garmin 国际直连" : "Garmin 中国区在线");
        } else if (hasCoros) {
          setWatchStatusLabel("COROS 高驰在线");
        } else {
          setWatchStatusLabel("未绑定手表 · 点击连接");
        }
      })
      .catch(() => {});
  }, []);

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
  }, [checkRole, loadNotifications]);

  const isSuperAdmin = Boolean(
    user &&
      (user.id === "admin" ||
        user.id === "super_admin" ||
        user.is_admin)
  );

  // Mobile 5-Tab Nav aligned with MiniApp
  const mobileNavItems = [
    { label: "首页", href: "/dashboard", icon: Activity, matchPaths: ["/dashboard"] },
    { label: "训练", href: "/dashboard/coach", icon: Zap, matchPaths: ["/dashboard/coach", "/dashboard/analysis"] },
    { label: "跑团", href: "/dashboard/team", icon: Users, matchPaths: ["/dashboard/team"] },
    ...(isCoachOrOwner
      ? [{ label: "教练", href: "/dashboard/team-coach", icon: ClipboardCheck, matchPaths: ["/dashboard/team-coach"] }]
      : []),
    { label: "我的", href: "/dashboard/profile", icon: User, matchPaths: ["/dashboard/profile"] },
  ];

  // Role-specific desktop sidebar navigation list
  const sidebarNavItems: {
    key: string;
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: string;
    isActive: boolean;
  }[] = (() => {
    const sp = new URLSearchParams(searchStr);
    const curTab = sp.get("tab") || "";
    const curMode = sp.get("mode") || "";
    const curOrgAct = sp.get("org_action") || "";
    const curOpen = sp.get("open") || "";

    if (rolePerspective === "leader") {
      return [
        {
          key: "captain",
          label: "团长驾驶舱",
          href: "/dashboard/team?tab=president",
          icon: Crown,
          isActive: pathname === "/dashboard/team" && curTab === "president" && curOpen !== "club-report",
        },
        {
          key: "radar",
          label: "选兔与约跑",
          href: "/dashboard/team?tab=events",
          icon: Target,
          isActive: pathname === "/dashboard/team" && curTab === "events",
        },
        {
          key: "teamcoach",
          label: "教练信号灯",
          href: "/dashboard/team-coach?tab=coach",
          icon: ClipboardCheck,
          badge: "雷达",
          isActive: (pathname === "/dashboard/team-coach" || (pathname === "/dashboard/team" && curTab === "coach")) && curMode !== "batch-critique",
        },
        {
          key: "critique",
          label: "5秒批阅排课",
          href: "/dashboard/team-coach?mode=batch-critique",
          icon: Sparkles,
          badge: "5s",
          isActive: (pathname === "/dashboard/team-coach" || pathname === "/dashboard/team") && curMode === "batch-critique",
        },
        {
          key: "report",
          label: "战报播报室",
          href: "/dashboard/team?tab=president&open=club-report",
          icon: BarChart3,
          isActive: pathname === "/dashboard/team" && curOpen === "club-report",
        },
      ];
    }

    if (rolePerspective === "admin") {
      return [
        {
          key: "orgaudit",
          label: "大群实名核验",
          href: hasManagedOrg ? "/dashboard/team?org_action=audit" : "/dashboard/admin?tab=orgs",
          icon: ShieldCheck,
          badge: "14天",
          isActive: (pathname === "/dashboard/team" && curOrgAct === "audit") || (pathname === "/dashboard/admin" && !curTab),
        },
        {
          key: "orgs",
          label: "大群与分团树",
          href: "/dashboard/admin?tab=orgs",
          icon: Shield,
          isActive: pathname === "/dashboard/admin" && (curTab === "orgs" || curTab === "clubs"),
        },
        {
          key: "unaffiliated",
          label: "自由跑者池",
          href: "/dashboard/admin?tab=unaffiliated",
          icon: Users,
          isActive: pathname === "/dashboard/admin" && curTab === "unaffiliated",
        },
        {
          key: "analytics",
          label: "全站增长遥测",
          href: "/dashboard/admin?tab=analytics",
          icon: BarChart3,
          isActive: pathname === "/dashboard/admin" && curTab === "analytics",
        },
        {
          key: "support",
          label: "设备与AI运维",
          href: "/dashboard/admin?tab=support",
          icon: Wrench,
          isActive: pathname === "/dashboard/admin" && curTab === "support",
        },
      ];
    }

    return [
      {
        key: "home",
        label: "首页工作台",
        href: "/dashboard",
        icon: Activity,
        isActive: pathname === "/dashboard",
      },
      {
        key: "coach",
        label: "Canova 训练",
        href: "/dashboard/coach",
        icon: Zap,
        badge: "AI",
        isActive: pathname === "/dashboard/coach",
      },
      {
        key: "analysis",
        label: "生理与轨迹",
        href: "/dashboard/analysis",
        icon: Compass,
        isActive: pathname === "/dashboard/analysis",
      },
      {
        key: "team",
        label: "跑团与大群",
        href: "/dashboard/team",
        icon: Users,
        isActive: pathname === "/dashboard/team" && curOrgAct !== "audit" && curTab !== "president",
      },
      {
        key: "profile",
        label: "档案与隐私",
        href: "/dashboard/profile",
        icon: User,
        badge: "14天",
        isActive: pathname === "/dashboard/profile",
      },
      {
        key: "manual",
        label: "帮助手册",
        href: "/dashboard/manual",
        icon: BookOpen,
        isActive: pathname === "/dashboard/manual",
      },
    ];
  })();

  function handleRoleSwitch(nextRole: RolePerspective) {
    setRolePerspective(nextRole);
    if (typeof window !== "undefined") {
      localStorage.setItem("rgm_role_perspective", nextRole);
    }
    const targetHref =
      nextRole === "leader"
        ? isCoachOrOwner || isSuperAdmin
          ? "/dashboard/team-coach"
          : "/dashboard/team?tab=president"
        : nextRole === "admin"
        ? hasManagedOrg && !isSuperAdmin
          ? "/dashboard/team?org_action=audit"
          : "/dashboard/admin?tab=orgs"
        : "/dashboard";
    dispatchRgmNavIntent(targetHref);
    router.push(targetHref);
  }

  function handleNavClick(href: string) {
    dispatchRgmNavIntent(href);
  }

  const isDashboardRoute = Boolean(pathname?.startsWith("/dashboard"));
  const displayName =
    profileDisplayName ||
    user?.display_name ||
    user?.user_metadata?.display_name ||
    user?.email ||
    "跑者";
  const pageMeta = resolvePageMeta(pathname, searchStr);

  const notificationBellBlock = user && (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          const next = !notifOpen;
          setNotifOpen(next);
          if (next && user?.id) loadNotifications(user.id);
        }}
        title="站内系统与教练通知"
        className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] transition cursor-pointer"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1.5 -right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-[#FC4C02] text-white text-[10px] font-black flex items-center justify-center">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {notifOpen && (
        <div className="absolute right-0 top-11 w-80 sm:w-96 max-h-[70vh] bg-[var(--rgm-card)] border border-[var(--rgm-border)] rounded-2xl shadow-2xl overflow-hidden z-50 flex flex-col">
          <div className="px-4 py-3 border-b border-[var(--rgm-border)] flex items-center justify-between">
            <span className="text-xs font-black text-[var(--rgm-text)]">
              消息中心 {unreadCount > 0 ? `(${unreadCount} 条未读)` : ""}
            </span>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllNotifsRead}
                  className="text-[11px] text-emerald-500 hover:text-emerald-400 font-bold flex items-center gap-1 cursor-pointer"
                >
                  <CheckCheck className="w-3 h-3" />
                  全部已读
                </button>
              )}
              <button
                type="button"
                onClick={() => setNotifOpen(false)}
                className="text-xs text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] cursor-pointer"
              >
                关闭
              </button>
            </div>
          </div>
          <div className="overflow-y-auto divide-y divide-[var(--rgm-divider)] max-h-80">
            {notifications.length === 0 ? (
              <div className="py-10 text-center text-xs text-[var(--rgm-text-muted)]">
                暂无新消息 · 教练点评与课表推送将在此显示
              </div>
            ) : (
              notifications.map((n: any) => (
                <div
                  key={n.id}
                  onClick={() => {
                    if (!n.is_read) handleMarkNotifRead(n.id);
                    if (n.link_url && typeof n.link_url === "string" && n.link_url.startsWith("/")) {
                      setNotifOpen(false);
                      dispatchRgmNavIntent(n.link_url);
                      router.push(n.link_url);
                    }
                  }}
                  className={`px-4 py-3 transition cursor-pointer hover:bg-[var(--rgm-card-2)] ${
                    !n.is_read ? "bg-[var(--rgm-brand-tint)]" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-xs font-bold text-[var(--rgm-text)] flex items-center gap-1.5">
                      {!n.is_read && <span className="w-1.5 h-1.5 rounded-full bg-[#FC4C02] shrink-0" />}
                      {n.title || "系统通知"}
                    </span>
                    <span className="text-[10px] text-[var(--rgm-text-muted)] shrink-0">
                      {String(n.created_at || "").slice(5, 16).replace("T", " ")}
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--rgm-text-2)] mt-1 leading-relaxed line-clamp-3">
                    {n.content}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );

  // Branch A: Public Portal & Auth Routes (W1.1 Topbar)
  if (!isDashboardRoute) {
    return (
      <>
        <header className="sticky top-0 z-50 backdrop-blur-md bg-[var(--rgm-topbar)]/95 border-b border-[var(--rgm-border)] transition-colors duration-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
            <Link href="/" className="flex items-center gap-2.5 font-black text-lg sm:text-xl tracking-tight whitespace-nowrap shrink-0">
              <img
                src="/logo.png"
                alt="万跑跑团助手 Logo"
                width={36}
                height={36}
                className="w-9 h-9 rounded-xl object-contain bg-white shadow-md shadow-[#FC4C02]/20 shrink-0"
              />
              <span className="text-[var(--rgm-text)]">
                万跑跑团助手{" "}
                <span className="text-[#FC4C02] text-xs font-bold ml-1 px-2 py-0.5 rounded-full bg-[#FC4C02]/10 border border-[#FC4C02]/30">
                  Web 3.0
                </span>
              </span>
            </Link>

            <nav className="hidden md:flex items-center gap-6 text-xs font-bold text-[var(--rgm-text-2)]">
              <Link href="/#ecosystem" className="hover:text-[var(--rgm-text)] transition">
                生态直连
              </Link>
              <Link href="/#canova" className="hover:text-[var(--rgm-text)] transition">
                Canova AI
              </Link>
              <Link href="/#clubs" className="hover:text-[var(--rgm-text)] transition">
                跑团生态
              </Link>
              <Link href="/dashboard/manual" className="hover:text-[var(--rgm-text)] transition">
                帮助手册
              </Link>
            </nav>

            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleToggleTheme}
                title={themeMode === "dark" ? "切换为 Volt Light v3.0 竞技亮色" : "切换为 Obsidian Dark 曜石暗黑"}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs font-bold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] transition cursor-pointer"
              >
                {themeMode === "dark" ? (
                  <>
                    <Sun className="w-3.5 h-3.5 text-amber-400" />
                    <span className="hidden sm:inline">明亮</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-3.5 h-3.5 text-[#FC4C02]" />
                    <span className="hidden sm:inline">暗黑</span>
                  </>
                )}
              </button>

              {user ? (
                <Link
                  href="/dashboard"
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] hover:bg-orange-600 text-white text-xs font-bold transition shadow-md shadow-[#FC4C02]/25"
                >
                  <Activity className="w-3.5 h-3.5" />
                  进入工作台
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => setAuthOpen(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FC4C02] hover:bg-orange-600 text-white text-xs font-bold transition shadow-md shadow-[#FC4C02]/25 cursor-pointer"
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

  // Branch B: Dashboard Workbench Shell (Fixed Left Role-Adaptive Sidebar + Top Command Bar + Mobile 5-Tab)
  return (
    <>
      {/* ── Fixed Left Role-Adaptive Sidebar (lg: 72px icon rail / xl: 224px full) ── */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 z-40 lg:w-[72px] xl:w-[224px] flex-col justify-between bg-[var(--rgm-sidebar)] border-r border-[var(--rgm-border)] transition-all duration-200">
        <div className="p-3 xl:p-3.5 space-y-4 overflow-y-auto no-scrollbar">
          {/* Brand Logo */}
          <Link
            href="/dashboard"
            onClick={() => handleNavClick("/dashboard")}
            className="flex items-center justify-center xl:justify-start gap-2.5 px-1 py-1"
          >
            <img
              src="/logo.png"
              alt="万跑跑团助手 Logo"
              width={32}
              height={32}
              className="w-8 h-8 rounded-xl object-contain bg-white shadow-sm shrink-0"
            />
            <div className="hidden xl:block min-w-0">
              <div className="text-sm font-black text-[var(--rgm-text)] leading-tight truncate">
                万跑跑团助手
              </div>
              <div className="text-[10px] font-bold text-[#FC4C02] tracking-wide">
                RGM Web 3.0
              </div>
            </div>
          </Link>

          {/* 3-Role Perspective Switcher (跑者 | 团/教 | 管理) */}
          <div className="hidden xl:block space-y-1.5">
            <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
              {(
                [
                  { key: "runner", label: "跑者" },
                  { key: "leader", label: "团/教" },
                  { key: "admin", label: "管理" },
                ] as const
              ).map((r) => {
                const act = rolePerspective === r.key;
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => handleRoleSwitch(r.key)}
                    className={`py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                      act
                        ? "bg-[#FC4C02] text-white shadow-sm"
                        : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)]"
                    }`}
                  >
                    {r.label}
                  </button>
                );
              })}
            </div>
            <div className="px-1 text-[10px] font-bold text-[var(--rgm-text-muted)]">
              {rolePerspective === "runner"
                ? "普通跑者视角"
                : rolePerspective === "leader"
                ? "团长 / 教练视角"
                : "大群 / 超管视角"}
            </div>
          </div>

          {/* Role-Adaptive Navigation List */}
          <nav className="space-y-1">
            {sidebarNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  title={item.label}
                  onClick={() => handleNavClick(item.href)}
                  className={`relative flex items-center justify-center xl:justify-between gap-2.5 px-2.5 xl:px-3 py-2.5 rounded-xl text-xs font-bold transition ${
                    item.isActive
                      ? "bg-[var(--rgm-brand-tint)] text-[#FC4C02] border border-[#FC4C02]/35"
                      : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)] border border-transparent"
                  }`}
                >
                  {item.isActive && (
                    <span className="hidden xl:block absolute left-0 top-2 bottom-2 w-[3px] rounded-r bg-[#FC4C02]" />
                  )}
                  <span className="flex items-center gap-2.5 min-w-0">
                    <Icon className="w-4 h-4 shrink-0" />
                    <span className="hidden xl:inline truncate">{item.label}</span>
                  </span>
                  {item.badge && (
                    <span
                      className={`hidden xl:inline-flex px-1.5 py-0.5 rounded-md text-[10px] font-extrabold shrink-0 ${
                        item.isActive
                          ? "bg-[#FC4C02] text-white"
                          : "bg-[var(--rgm-card-3)] text-[var(--rgm-text-muted)]"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Bottom Watch Status & Dual-Theme Switcher */}
        <div className="p-3 xl:p-3.5 space-y-2.5 border-t border-[var(--rgm-border)]">
          <Link
            href="/dashboard/profile?tab=device"
            onClick={() => handleNavClick("/dashboard/profile?tab=device")}
            title={watchStatusLabel}
            className="flex items-center justify-center xl:justify-start gap-2.5 p-2.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/40 transition"
          >
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                watchConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
              }`}
            />
            <div className="hidden xl:block min-w-0">
              <div className="text-[11px] font-bold text-[var(--rgm-text)] leading-tight flex items-center gap-1">
                <Watch className="w-3 h-3 text-[#FC4C02]" />
                手表实时直连
              </div>
              <div
                className={`text-[10px] font-semibold truncate mt-0.5 ${
                  watchConnected ? "text-emerald-500" : "text-amber-500"
                }`}
              >
                {watchStatusLabel}
              </div>
            </div>
          </Link>

          {/* Compact Toggle for lg (icon-only rail) */}
          <button
            type="button"
            onClick={handleToggleTheme}
            title={themeMode === "dark" ? "切换明亮模式" : "切换暗黑模式"}
            className="xl:hidden w-full h-9 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] flex items-center justify-center text-[var(--rgm-text-2)] cursor-pointer"
          >
            {themeMode === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-[#FC4C02]" />}
          </button>

          {/* Full Dual-Theme Segmented Pill (暗黑 | 明亮) for xl */}
          <div className="hidden xl:grid grid-cols-2 gap-1 p-1 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)]">
            <button
              type="button"
              onClick={() => {
                if (themeMode !== "dark") handleToggleTheme();
              }}
              className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                themeMode === "dark"
                  ? "bg-[var(--rgm-card-3)] text-[var(--rgm-text)] border border-[var(--rgm-border)] shadow-sm"
                  : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
              }`}
            >
              <Moon className="w-3 h-3" />
              暗黑
            </button>
            <button
              type="button"
              onClick={() => {
                if (themeMode !== "light") handleToggleTheme();
              }}
              className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] font-bold transition cursor-pointer ${
                themeMode === "light"
                  ? "bg-[#FC4C02] text-white shadow-sm"
                  : "text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)]"
              }`}
            >
              <Sun className="w-3 h-3" />
              明亮
            </button>
          </div>
        </div>
      </aside>

      {/* ── Top Sticky Global Command Bar ── */}
      <header className="sticky top-0 z-30 lg:pl-[72px] xl:pl-[224px] bg-[var(--rgm-topbar)]/95 backdrop-blur-md border-b border-[var(--rgm-border)] transition-colors duration-200">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
          {/* Mobile Brand (<lg) */}
          <Link
            href="/dashboard"
            onClick={() => handleNavClick("/dashboard")}
            className="flex lg:hidden items-center gap-2 font-black text-base tracking-tight whitespace-nowrap shrink-0"
          >
            <img
              src="/logo.png"
              alt="万跑跑团助手 Logo"
              width={32}
              height={32}
              className="w-8 h-8 rounded-lg object-contain bg-white shadow-sm shrink-0"
            />
            <span className="text-[var(--rgm-text)]">万跑助手</span>
          </Link>

          {/* Desktop Dynamic Context Page Title & Subtitle */}
          <div className="hidden lg:block min-w-0">
            <div className="text-sm font-black text-[var(--rgm-text)] truncate">{pageMeta.title}</div>
            <div className="text-[11px] text-[var(--rgm-text-muted)] truncate">{pageMeta.subtitle}</div>
          </div>

          {/* Global Search (⌘K) + Utility Controls */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden md:flex items-center justify-between gap-3 w-56 lg:w-64 px-3 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text-muted)] hover:border-[#FC4C02]/45 hover:text-[var(--rgm-text)] transition cursor-pointer"
            >
              <span className="flex items-center gap-2 truncate">
                <Search className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">搜索跑者 / 课表 / 跑团</span>
              </span>
              <kbd className="px-1.5 py-0.5 rounded bg-[var(--rgm-card-3)] text-[10px] font-bold shrink-0">
                ⌘K
              </kbd>
            </button>

            {user?.id && (
              <button
                type="button"
                onClick={() => window.dispatchEvent(new CustomEvent("rgm-open-coach-chat"))}
                title="打开 Canova AI 教练对话舱"
                className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--rgm-blue-tint)] border border-sky-500/35 text-sky-400 text-xs font-bold hover:opacity-90 transition cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5" />
                <span className="hidden xl:inline">AI 教练</span>
              </button>
            )}

            {/* Mobile Theme Toggle */}
            <button
              type="button"
              onClick={handleToggleTheme}
              title={themeMode === "dark" ? "切换为明亮模式" : "切换为暗黑模式"}
              className="flex lg:hidden items-center justify-center w-9 h-9 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] cursor-pointer"
            >
              {themeMode === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-[#FC4C02]" />}
            </button>

            {notificationBellBlock}

            {user ? (
              <div className="flex items-center gap-2 pl-1">
                <Link
                  href="/dashboard/profile"
                  className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/40 transition"
                >
                  <span className="w-6 h-6 rounded-full bg-[#FC4C02] text-white text-[11px] font-black flex items-center justify-center shrink-0">
                    {String(displayName || "跑").slice(0, 1)}
                  </span>
                  <span className="hidden xl:inline text-xs font-bold text-[var(--rgm-text)] max-w-[100px] truncate">
                    {displayName}
                  </span>
                </Link>
                <button
                  type="button"
                  onClick={() => supabase.auth.signOut()}
                  title="退出登录"
                  className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs font-semibold text-[var(--rgm-text-muted)] hover:text-rose-400 transition cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5 shrink-0" />
                  <span className="hidden sm:inline">退出</span>
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setAuthOpen(true)}
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#FC4C02] text-white text-xs font-bold hover:bg-orange-600 transition cursor-pointer"
              >
                <LogIn className="w-3.5 h-3.5 shrink-0" />
                登录
              </button>
            )}
          </div>
        </div>

        {/* Mobile / Narrow Window 5-Tab Bar (W10.4 aligned with MiniApp) */}
        <nav className="flex lg:hidden items-center justify-around gap-1 px-3 pb-2.5 overflow-x-auto no-scrollbar border-t border-[var(--rgm-divider)] pt-2">
          {mobileNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.matchPaths.includes(pathname || "");
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => handleNavClick(item.href)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap shrink-0 transition-all ${
                  isActive
                    ? "bg-[#FC4C02] text-white shadow-sm"
                    : "text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)]"
                }`}
              >
                <Icon className="w-3.5 h-3.5 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>

      <AuthModal open={authOpen} onClose={() => setAuthOpen(false)} />
      <CommandPaletteModal
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        isCoachOrOwner={isCoachOrOwner}
        isSuperAdmin={isSuperAdmin}
        hasManagedOrg={hasManagedOrg}
        themeMode={themeMode}
        onToggleTheme={handleToggleTheme}
      />
      {user?.id && isDashboardRoute && (
        <CoachChatBox uid={user.id} hideFloatingOnXl={pathname === "/dashboard/coach"} />
      )}
    </>
  );
}
