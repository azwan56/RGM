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
  Watch,
  Mic,
  Calendar,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import AuthModal from "./AuthModal";
import CoachChatBox from "./CoachChatBox";
import CommandPaletteModal, { dispatchRgmNavIntent } from "./web3/CommandPaletteModal";
import AiOperationAssistant, { openAiOperationAssistant } from "./web3/AiOperationAssistant";

function resolvePageContext(
  pathname: string | null,
  searchStr: string
): { group: string; title: string; subtitle: string } {
  const sp = new URLSearchParams(searchStr || "");
  const tab = sp.get("tab") || "";
  const mode = sp.get("mode") || "";
  const orgAction = sp.get("org_action") || "";

  if (pathname === "/dashboard/coach") {
    if (tab === "report") {
      return {
        group: "训练",
        title: "周期训练报告",
        subtitle: "多赛事备赛节奏与各阶段训练强度概览",
      };
    }
    return {
      group: "训练",
      title: "AI 教练与课表",
      subtitle: "每周动态训练课表 · 双栏 AI 教练实时调课",
    };
  }
  if (pathname === "/dashboard/analysis") {
    return {
      group: "训练",
      title: "生理与轨迹",
      subtitle: "有效跑力变化 · 赛前减量参考 · 完赛能力评估",
    };
  }
  if (pathname === "/dashboard/discover") {
    return {
      group: "跑团",
      title: "同频寻搭子",
      subtitle: "按配速与活动范围筛选同城训练伙伴，互相关注并对比周跑量",
    };
  }
  if (pathname === "/dashboard/plaza") {
    return {
      group: "跑团",
      title: "选团与名帅",
      subtitle: "浏览本地认证跑团、教练资质与日常合练风采",
    };
  }
  if (
    pathname === "/dashboard/team-coach" ||
    (pathname === "/dashboard/team" && (tab === "coach" || mode === "batch-critique"))
  ) {
    if (mode === "batch-critique") {
      return {
        group: "管理",
        title: "连续批阅排课",
        subtitle: "按异常优先级集中审阅队员训练并快速发送反馈",
      };
    }
    return {
      group: "管理",
      title: "教练工作台",
      subtitle: "查看全团体能状态分布、出勤情况与快速调课",
    };
  }
  if (pathname === "/dashboard/team") {
    if (orgAction === "audit") {
      return {
        group: "管理",
        title: "大群实名核验",
        subtitle: "核验大群成员身份信息与入群资格状态",
      };
    }
    if (tab === "president") {
      return {
        group: "管理",
        title: "团长驾驶舱",
        subtitle: "全团达标概览 · 邀请码生成与成员角色管理",
      };
    }
    if (tab === "events") {
      return {
        group: "跑团",
        title: "约跑活动",
        subtitle: "按配速分队报名周末合练与赛前配速列车",
      };
    }
    return {
      group: "跑团",
      title: "我的跑团",
      subtitle: "查看跑团动态、完成率与跑量双模排行榜",
    };
  }
  if (pathname === "/dashboard/profile") {
    if (tab === "device") {
      return {
        group: "账户",
        title: "手表绑定",
        subtitle: "连接 Garmin（中国区 / 国际区）或 COROS 高驰自动同步跑步记录",
      };
    }
    if (tab === "training") {
      return {
        group: "账户",
        title: "赛事与目标",
        subtitle: "管理全年 A/B/C 目标赛事与阶段跑量规划",
      };
    }
    return {
      group: "账户",
      title: "档案与隐私",
      subtitle: "个人跑力档案、绑定状态与展示范围设置",
    };
  }
  if (pathname === "/dashboard/admin") {
    if (tab === "analytics") {
      return {
        group: "管理",
        title: "增长与数据概览",
        subtitle: "双端活跃度、绑定转化漏斗与使用趋势统计",
      };
    }
    if (tab === "support") {
      return {
        group: "管理",
        title: "设备与服务运维",
        subtitle: "手表同步通道状态检查与常见异常排查",
      };
    }
    if (tab === "unaffiliated") {
      return {
        group: "管理",
        title: "自由跑者池",
        subtitle: "管理已绑定手表但尚未加入跑团的跑友并发送邀请",
      };
    }
    if (tab === "clubs") {
      return {
        group: "管理",
        title: "跑团管理",
        subtitle: "新建或编辑跑团信息、指派团长并管理跑团状态",
      };
    }
    return {
      group: "管理",
      title: "平台总控台",
      subtitle: "管理大群与分团结构、成员核验及平台运维",
    };
  }
  if (pathname === "/dashboard/manual") {
    return {
      group: "账户",
      title: "帮助手册",
      subtitle: "新手指引、佳明双区切换与常见问题解答",
    };
  }
  return {
    group: "训练",
    title: "首页工作台",
    subtitle: "今日训练任务、周跑量进度与跑团近期动态",
  };
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [themeMode, setThemeMode] = useState<"dark" | "light">("dark");
  const [notifOpen, setNotifOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [hasManagedOrg, setHasManagedOrg] = useState(false);
  const [watchStatusLabel, setWatchStatusLabel] = useState("未绑定手表");
  const [watchConnected, setWatchConnected] = useState(false);
  const [profileDisplayName, setProfileDisplayName] = useState("");
  const [searchStr, setSearchStr] = useState("");

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

  // Track URL query string & close transient menus on navigation
  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncFromUrl = (customHref?: string) => {
      const q = customHref && customHref.includes("?")
        ? `?${customHref.split("?")[1]}`
        : window.location.search;
      setSearchStr(q);
      setUserMenuOpen(false);
      setNotifOpen(false);
    };

    syncFromUrl();
    const onPop = () => syncFromUrl();
    const onNavIntent = (e: Event) => {
      const detail = (e as CustomEvent)?.detail;
      const href = detail?.href;
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

  const sp = new URLSearchParams(searchStr);
  const curTab = sp.get("tab") || "";
  const curMode = sp.get("mode") || "";
  const curOrgAct = sp.get("org_action") || "";
  const canCoach = Boolean(isCoachOrOwner || isSuperAdmin);
  const canManage = Boolean(isCoachOrOwner || hasManagedOrg || isSuperAdmin);

  // Mobile 5-Tab Nav aligned 1:1 with desktop groups
  const mobileNavItems: {
    key: string;
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    isActive: boolean;
  }[] = [
    {
      key: "home",
      label: "首页",
      href: "/dashboard",
      icon: Activity,
      isActive: pathname === "/dashboard",
    },
    {
      key: "train",
      label: "训练",
      href: "/dashboard/coach",
      icon: Zap,
      isActive: pathname === "/dashboard/coach" || pathname === "/dashboard/analysis",
    },
    {
      key: "team",
      label: "跑团",
      href: "/dashboard/team",
      icon: Users,
      isActive: canManage
        ? pathname === "/dashboard/discover" ||
          pathname === "/dashboard/plaza" ||
          (pathname === "/dashboard/team" &&
            curOrgAct !== "audit" &&
            curTab !== "coach" &&
            curTab !== "president" &&
            curMode !== "batch-critique")
        : pathname === "/dashboard/team" && curOrgAct !== "audit",
    },
    canManage
      ? {
          key: "manage",
          label: "管理",
          href: canCoach
            ? "/dashboard/team?tab=coach"
            : hasManagedOrg && !isSuperAdmin
            ? "/dashboard/team?org_action=audit"
            : "/dashboard/admin?tab=orgs",
          icon: ClipboardCheck,
          isActive:
            pathname === "/dashboard/team-coach" ||
            pathname === "/dashboard/admin" ||
            (pathname === "/dashboard/team" &&
              (curOrgAct === "audit" ||
                curTab === "coach" ||
                curTab === "president" ||
                curMode === "batch-critique")),
        }
      : {
          key: "discover",
          label: "发现",
          href: "/dashboard/discover",
          icon: Target,
          isActive: pathname === "/dashboard/discover" || pathname === "/dashboard/plaza",
        },
    {
      key: "me",
      label: "我的",
      href: "/dashboard/profile",
      icon: User,
      isActive: pathname === "/dashboard/profile" || pathname === "/dashboard/manual",
    },
  ];

  type SidebarNavItem = {
    key: string;
    label: string;
    href: string;
    icon: React.ComponentType<{ className?: string }>;
    isActive: boolean;
    statusDot?: "connected" | "disconnected";
    statusTitle?: string;
  };

  type SidebarNavGroup = {
    key: string;
    label: string;
    items: SidebarNavItem[];
  };

  const manageItems: SidebarNavItem[] = [
    ...(canCoach
      ? [
          {
            key: "teamcoach",
            label: "教练工作台",
            href: "/dashboard/team?tab=coach",
            icon: ClipboardCheck,
            isActive:
              pathname === "/dashboard/team-coach" ||
              (pathname === "/dashboard/team" && (curTab === "coach" || curMode === "batch-critique")),
          },
          {
            key: "captain",
            label: "团长驾驶舱",
            href: "/dashboard/team?tab=president",
            icon: Crown,
            isActive: pathname === "/dashboard/team" && curTab === "president",
          },
        ]
      : []),
    ...(hasManagedOrg && !isSuperAdmin
      ? [
          {
            key: "orgaudit",
            label: "大群实名核验",
            href: "/dashboard/team?org_action=audit",
            icon: ShieldCheck,
            isActive: (pathname === "/dashboard/team" && curOrgAct === "audit") || pathname === "/dashboard/admin",
          },
        ]
      : []),
    ...(isSuperAdmin
      ? [
          {
            key: "admin",
            label: "平台总控台",
            href: "/dashboard/admin?tab=orgs",
            icon: Shield,
            isActive: pathname === "/dashboard/admin" || (pathname === "/dashboard/team" && curOrgAct === "audit"),
          },
        ]
      : []),
  ];

  // Permanent 4-group sidebar navigation (no role-switching disorientation)
  const sidebarNavGroups: SidebarNavGroup[] = [
    {
      key: "training",
      label: "训练",
      items: [
        {
          key: "home",
          label: "首页工作台",
          href: "/dashboard",
          icon: Activity,
          isActive: pathname === "/dashboard",
        },
        {
          key: "coach",
          label: "AI 教练与课表",
          href: "/dashboard/coach",
          icon: Zap,
          isActive: pathname === "/dashboard/coach",
        },
        {
          key: "analysis",
          label: "生理与轨迹",
          href: "/dashboard/analysis",
          icon: Compass,
          isActive: pathname === "/dashboard/analysis",
        },
      ],
    },
    {
      key: "club",
      label: "跑团",
      items: [
        {
          key: "team",
          label: "我的跑团",
          href: "/dashboard/team",
          icon: Users,
          isActive:
            pathname === "/dashboard/team" &&
            curOrgAct !== "audit" &&
            curTab !== "events" &&
            curTab !== "coach" &&
            curTab !== "president" &&
            curMode !== "batch-critique",
        },
        {
          key: "events",
          label: "约跑活动",
          href: "/dashboard/team?tab=events",
          icon: Calendar,
          isActive: pathname === "/dashboard/team" && curTab === "events",
        },
        {
          key: "discover",
          label: "同频寻搭子",
          href: "/dashboard/discover",
          icon: Target,
          isActive: pathname === "/dashboard/discover",
        },
        {
          key: "plaza",
          label: "选团与名帅",
          href: "/dashboard/plaza",
          icon: Sparkles,
          isActive: pathname === "/dashboard/plaza",
        },
      ],
    },
    ...(manageItems.length > 0
      ? [
          {
            key: "manage",
            label: "管理",
            items: manageItems,
          },
        ]
      : []),
    {
      key: "account",
      label: "账户",
      items: [
        {
          key: "profile",
          label: "档案与隐私",
          href: "/dashboard/profile",
          icon: User,
          isActive: pathname === "/dashboard/profile" && curTab !== "device",
        },
        {
          key: "watch",
          label: "手表绑定",
          href: "/dashboard/profile?tab=device",
          icon: Watch,
          isActive: pathname === "/dashboard/profile" && curTab === "device",
          statusDot: watchConnected ? "connected" : "disconnected",
          statusTitle: watchStatusLabel,
        },
        {
          key: "manual",
          label: "帮助手册",
          href: "/dashboard/manual",
          icon: BookOpen,
          isActive: pathname === "/dashboard/manual",
        },
      ],
    },
  ];

  function handleNavClick(href: string) {
    setUserMenuOpen(false);
    setNotifOpen(false);
    dispatchRgmNavIntent(href);
  }

  const isDashboardRoute = Boolean(pathname?.startsWith("/dashboard"));
  const displayName =
    profileDisplayName ||
    user?.display_name ||
    user?.user_metadata?.display_name ||
    user?.email ||
    "跑者";
  const pageMeta = resolvePageContext(pathname, searchStr);

  const notificationBellBlock = user && (
    <div className="relative">
      <button
        type="button"
        onClick={() => {
          const next = !notifOpen;
          setNotifOpen(next);
          if (next) setUserMenuOpen(false);
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
                onClick={() => openAiOperationAssistant()}
                title="AI 操作助手：输入或语音说出目的，直接带你去对应入口 (⌘/)"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--rgm-brand-tint)] border border-[#FC4C02]/35 text-xs font-extrabold text-[#FC4C02] hover:bg-[#FC4C02] hover:text-white transition cursor-pointer"
              >
                <Mic className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden sm:inline">AI 操作助手</span>
                <span className="sm:hidden">向导</span>
              </button>

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
        <AiOperationAssistant
          user={user}
          isCoachOrOwner={isCoachOrOwner}
          isSuperAdmin={isSuperAdmin}
          hasManagedOrg={hasManagedOrg}
          themeMode={themeMode}
          onToggleTheme={handleToggleTheme}
          onOpenAuth={() => setAuthOpen(true)}
        />
      </>
    );
  }

  // Branch B: Dashboard Workbench Shell (Fixed Permanent Grouped Sidebar + Top Command Bar + Mobile 5-Tab)
  return (
    <>
      {/* ── Fixed Left Permanent Grouped Sidebar (lg: 72px icon rail / xl: 224px full) ── */}
      <aside className="hidden lg:flex fixed inset-y-0 left-0 z-40 lg:w-[72px] xl:w-[224px] flex-col justify-between bg-[var(--rgm-sidebar)] border-r border-[var(--rgm-border)] transition-all duration-200">
        <div className="p-3 xl:p-3.5 space-y-3 overflow-y-auto no-scrollbar">
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

          {/* Permanent 4-Group Navigation List */}
          <nav className="space-y-1">
            {sidebarNavGroups.map((group, groupIdx) => (
              <div key={group.key} className="space-y-0.5">
                {groupIdx > 0 && (
                  <div className="xl:hidden h-px bg-[var(--rgm-border)] mx-2 my-2" />
                )}
                <div
                  className={`hidden xl:block px-3 pb-1 text-[10px] font-black uppercase tracking-wider text-[var(--rgm-text-muted)] ${
                    groupIdx === 0 ? "pt-1" : "pt-3"
                  }`}
                >
                  {group.label}
                </div>
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.key}
                      href={item.href}
                      title={item.statusTitle ? `${item.label} · ${item.statusTitle}` : item.label}
                      onClick={() => handleNavClick(item.href)}
                      className={`relative flex items-center justify-center xl:justify-between gap-2.5 px-2.5 xl:px-3 py-2 rounded-xl text-xs font-bold transition ${
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
                      {item.statusDot && (
                        <span
                          title={item.statusTitle}
                          className={`hidden xl:inline-block w-2 h-2 rounded-full shrink-0 ${
                            item.statusDot === "connected" ? "bg-emerald-500" : "bg-amber-500"
                          }`}
                        />
                      )}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* Single Bottom Theme Switcher */}
        <div className="p-3 xl:p-3.5 border-t border-[var(--rgm-border)]">
          <button
            type="button"
            onClick={handleToggleTheme}
            title={themeMode === "dark" ? "切换明亮模式" : "切换暗黑模式"}
            className="w-full h-9 px-2.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/40 flex items-center justify-center xl:justify-start gap-2 text-xs font-bold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] transition cursor-pointer"
          >
            {themeMode === "dark" ? (
              <Sun className="w-4 h-4 text-amber-400 shrink-0" />
            ) : (
              <Moon className="w-4 h-4 text-[#FC4C02] shrink-0" />
            )}
            <span className="hidden xl:inline truncate">
              {themeMode === "dark" ? "切换明亮" : "切换暗黑"}
            </span>
          </button>
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

          {/* Desktop Dynamic Context Breadcrumb & Subtitle */}
          <div className="hidden lg:block min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <span className="text-[11px] font-bold text-[var(--rgm-text-muted)] shrink-0">
                {pageMeta.group}
              </span>
              <ChevronRight className="w-3 h-3 text-[var(--rgm-text-muted)] shrink-0" />
              <div className="text-sm font-black text-[var(--rgm-text)] truncate">
                {pageMeta.title}
              </div>
            </div>
            <div className="text-[11px] text-[var(--rgm-text-muted)] truncate mt-0.5">
              {pageMeta.subtitle}
            </div>
          </div>

          {/* Global Search (⌘K) + Deduplicated Utility Controls */}
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden md:flex items-center justify-between gap-3 w-56 lg:w-64 px-3 py-1.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-xs text-[var(--rgm-text-muted)] hover:border-[#FC4C02]/45 hover:text-[var(--rgm-text)] transition cursor-pointer"
            >
              <span className="flex items-center gap-2 truncate">
                <Search className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">搜索功能 / 跑者 / 跑团</span>
              </span>
              <kbd className="px-1.5 py-0.5 rounded bg-[var(--rgm-card-3)] text-[10px] font-bold shrink-0">
                ⌘K
              </kbd>
            </button>

            <button
              type="button"
              onClick={() => openAiOperationAssistant()}
              title="语音/文字操作向导：说出想做的事，直接带你过去 (⌘/)"
              aria-label="操作向导"
              className="w-9 h-9 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/45 text-[#FC4C02] flex items-center justify-center transition cursor-pointer shrink-0"
            >
              <Mic className="w-4 h-4" />
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

            {!user && (
              <button
                type="button"
                onClick={handleToggleTheme}
                title={themeMode === "dark" ? "切换为明亮模式" : "切换为暗黑模式"}
                className="flex lg:hidden items-center justify-center w-9 h-9 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[var(--rgm-text-2)] cursor-pointer"
              >
                {themeMode === "dark" ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-[#FC4C02]" />}
              </button>
            )}

            {notificationBellBlock}

            {user ? (
              <div className="relative pl-1">
                <button
                  type="button"
                  onClick={() => {
                    const next = !userMenuOpen;
                    setUserMenuOpen(next);
                    if (next) setNotifOpen(false);
                  }}
                  aria-expanded={userMenuOpen}
                  title={displayName}
                  className="flex items-center gap-2 px-2 py-1 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] hover:border-[#FC4C02]/40 transition cursor-pointer"
                >
                  <span className="w-6 h-6 rounded-full bg-[#FC4C02] text-white text-[11px] font-black flex items-center justify-center shrink-0">
                    {String(displayName || "跑").slice(0, 1)}
                  </span>
                  <span className="hidden xl:inline text-xs font-bold text-[var(--rgm-text)] max-w-[100px] truncate">
                    {displayName}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-[var(--rgm-text-muted)] shrink-0" />
                </button>

                {userMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-40"
                      onClick={() => setUserMenuOpen(false)}
                    />
                    <div className="absolute right-0 top-11 w-56 bg-[var(--rgm-card)] border border-[var(--rgm-border)] rounded-2xl shadow-2xl overflow-hidden z-50 py-1.5">
                      <div className="px-3.5 py-2.5 border-b border-[var(--rgm-border)]">
                        <div className="text-xs font-black text-[var(--rgm-text)] truncate">
                          {displayName}
                        </div>
                        <div className="flex items-center gap-1.5 mt-1 text-[10px] font-semibold text-[var(--rgm-text-muted)] truncate">
                          <span
                            className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                              watchConnected ? "bg-emerald-500" : "bg-amber-500"
                            }`}
                          />
                          <span className="truncate">{watchStatusLabel}</span>
                        </div>
                      </div>

                      <div className="py-1">
                        <Link
                          href="/dashboard/profile"
                          onClick={() => handleNavClick("/dashboard/profile")}
                          className="flex items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)] transition"
                        >
                          <User className="w-3.5 h-3.5 shrink-0" />
                          我的档案
                        </Link>
                        <Link
                          href="/dashboard/profile?tab=device"
                          onClick={() => handleNavClick("/dashboard/profile?tab=device")}
                          className="flex items-center justify-between gap-2 px-3.5 py-2 text-xs font-semibold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)] transition"
                        >
                          <span className="flex items-center gap-2.5">
                            <Watch className="w-3.5 h-3.5 shrink-0" />
                            手表绑定
                          </span>
                          <span
                            className={`text-[10px] font-bold ${
                              watchConnected ? "text-emerald-500" : "text-amber-500"
                            }`}
                          >
                            {watchConnected ? "已连接" : "未绑定"}
                          </span>
                        </Link>
                        <button
                          type="button"
                          onClick={() => {
                            handleToggleTheme();
                            setUserMenuOpen(false);
                          }}
                          className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)] transition cursor-pointer text-left"
                        >
                          {themeMode === "dark" ? (
                            <Sun className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                          ) : (
                            <Moon className="w-3.5 h-3.5 text-[#FC4C02] shrink-0" />
                          )}
                          {themeMode === "dark" ? "切换明亮" : "切换暗黑"}
                        </button>
                        <Link
                          href="/dashboard/manual"
                          onClick={() => handleNavClick("/dashboard/manual")}
                          className="flex items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-[var(--rgm-text-2)] hover:text-[var(--rgm-text)] hover:bg-[var(--rgm-card-2)] transition"
                        >
                          <BookOpen className="w-3.5 h-3.5 shrink-0" />
                          帮助手册
                        </Link>
                      </div>

                      <div className="border-t border-[var(--rgm-border)] mt-1 pt-1">
                        <button
                          type="button"
                          onClick={() => {
                            setUserMenuOpen(false);
                            supabase.auth.signOut();
                          }}
                          className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-500/10 transition cursor-pointer text-left"
                        >
                          <LogOut className="w-3.5 h-3.5 shrink-0" />
                          退出登录
                        </button>
                      </div>
                    </div>
                  </>
                )}
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

        {/* Mobile / Narrow Window 5-Tab Bar */}
        <nav className="flex lg:hidden items-center justify-around gap-1 px-3 pb-2.5 overflow-x-auto no-scrollbar border-t border-[var(--rgm-divider)] pt-2">
          {mobileNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.key}
                href={item.href}
                onClick={() => handleNavClick(item.href)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap shrink-0 transition-all ${
                  item.isActive
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
      <AiOperationAssistant
        user={user}
        isCoachOrOwner={isCoachOrOwner}
        isSuperAdmin={isSuperAdmin}
        hasManagedOrg={hasManagedOrg}
        themeMode={themeMode}
        onToggleTheme={handleToggleTheme}
        onOpenAuth={() => setAuthOpen(true)}
      />
    </>
  );
}
