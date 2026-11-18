"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  BarChart3,
  BookOpen,
  ClipboardCheck,
  Command,
  Compass,
  CornerDownLeft,
  Crown,
  Flame,
  Moon,
  Search,
  Shield,
  Sparkles,
  Sun,
  Target,
  Trophy,
  User,
  Users,
  Watch,
  Wrench,
  X,
  Zap,
} from "lucide-react";

export interface CommandPaletteItem {
  id: string;
  group: "runner" | "leader" | "admin" | "actions";
  label: string;
  desc: string;
  href?: string;
  keywords: string;
  badge?: string;
  icon: React.ComponentType<{ className?: string }>;
  action?: () => void;
}

interface CommandPaletteModalProps {
  open: boolean;
  onClose: () => void;
  isCoachOrOwner: boolean;
  isSuperAdmin: boolean;
  hasManagedOrg: boolean;
  themeMode: "dark" | "light";
  onToggleTheme: () => void;
}

const GROUP_LABELS: Record<CommandPaletteItem["group"], string> = {
  runner: "普通跑者工作台 · W1–W2 / W6–W8",
  leader: "团长与教练工作台 · W3–W4 / W9",
  admin: "大群管理员与平台超管 · W5 / W9.4",
  actions: "全局快捷指令 · Quick Actions",
};

export function dispatchRgmNavIntent(href: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent("rgm-nav-intent", { detail: { href } }));
}

export default function CommandPaletteModal({
  open,
  onClose,
  isCoachOrOwner,
  isSuperAdmin,
  hasManagedOrg,
  themeMode,
  onToggleTheme,
}: CommandPaletteModalProps) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  const items = useMemo<CommandPaletteItem[]>(() => {
    const list: CommandPaletteItem[] = [
      {
        id: "runner-home",
        group: "runner",
        label: "跑者全息工作台",
        desc: "今日 Canova 处方 · 三维跑量圆环 · 30天 PMC 负荷曲线 · 团榜",
        href: "/dashboard",
        keywords: "首页 工作台 bento dashboard 今日 课表 rpe",
        badge: "W1.2",
        icon: Activity,
      },
      {
        id: "runner-plan",
        group: "runner",
        label: "Canova 科学训练课表",
        desc: "W1–W8 周期化动态矩阵 · 右侧固定 Canova AI 调课舱 · 历史版本",
        href: "/dashboard/coach?tab=plan",
        keywords: "训练 课表 canova plan 调课 版本 回滚 打卡",
        badge: "W1.3",
        icon: Zap,
      },
      {
        id: "runner-report",
        group: "runner",
        label: "Canova 战略诊断报告",
        desc: "多赛事周期路线图 · A/B/C 优先级冲突诊断 · 6 级专项配速区间",
        href: "/dashboard/coach?tab=report",
        keywords: "诊断 报告 macrocycle 赛事 冲突 canova",
        badge: "W6.1",
        icon: Target,
      },
      {
        id: "runner-analysis",
        group: "runner",
        label: "生理数据、Taper 推演与官兔评估",
        desc: "VDOT · 五维耐力系数 · 赛前减量三方案推演 · 4K 战报海报",
        href: "/dashboard/analysis",
        keywords: "分析 生理 vdot taper 减量 官兔 pacer 战报",
        badge: "W1.4",
        icon: Compass,
      },
      {
        id: "runner-team",
        group: "runner",
        label: "跑团社交主页与竞跑榜",
        desc: "完成率/跑量双模榜 · 教练精评蓝框 · 团长加油 · 师徒结对",
        href: "/dashboard/team?tab=leaderboard",
        keywords: "跑团 社交 榜单 动态 师徒 邀请",
        badge: "W2.1",
        icon: Trophy,
      },
      {
        id: "runner-events",
        group: "runner",
        label: "周末约跑配速列车",
        desc: "门岗地图锚点 · 300/315/330/400 配速列车上车 · 赛后完赛战报",
        href: "/dashboard/team?tab=events",
        keywords: "约跑 活动 合练 列车 官兔 门岗",
        badge: "W2.2",
        icon: Users,
      },
      {
        id: "runner-discover",
        group: "runner",
        label: "六维同频寻搭子",
        desc: "5岁年龄段 · VDOT同频±2 · 30日跑量 · 公园地标 · 互关周PK",
        href: "/dashboard/discover",
        keywords: "搭子 找跑友 同频 搜索 关注 pk 公园 地标",
        badge: "W11.3",
        icon: Compass,
      },
      {
        id: "runner-plaza",
        group: "runner",
        label: "选团与名帅风采展厅",
        desc: "跑团品牌主页 · 手表核验防伪PB · 教练资历证书与合练照片墙",
        href: "/dashboard/plaza",
        keywords: "选团 宣传页 教练 资历 展厅 照片 相册",
        badge: "W13.1",
        icon: Trophy,
      },
      {
        id: "runner-profile",
        group: "runner",
        label: "三栏实名与 4 级隐私中心",
        desc: "14 天大群准入 · AES-256 脱敏资料 · 月度跑量柱图 · 4 级隐私开关",
        href: "/dashboard/profile",
        keywords: "档案 隐私 实名 aes 脱敏 清除",
        badge: "W2.4",
        icon: User,
      },
      {
        id: "runner-device",
        group: "runner",
        label: "运动手表双区直连设置",
        desc: "Garmin 中国区 (garmin.cn) / 国际区 · COROS 高驰直连 · PB 导入",
        href: "/dashboard/profile?tab=device",
        keywords: "手表 佳明 garmin 高驰 coros 绑定 同步",
        badge: "W2.4",
        icon: Watch,
      },
      {
        id: "runner-training-archive",
        group: "runner",
        label: "赛事档案、AI 情报与完赛荣誉墙",
        desc: "备赛计划 A/B/C · 联网AI赛事情报 · 手表自动匹配成绩与证书",
        href: "/dashboard/profile?tab=training",
        keywords: "赛事 档案 完赛 成绩 照片 情报 pb",
        badge: "W6.4",
        icon: Flame,
      },
      {
        id: "runner-manual",
        group: "runner",
        label: "新用户操作手册与 FAQ",
        desc: "佳明双区切换排查 · 14天实名解冻说明 · 隐私加密机制",
        href: "/dashboard/manual",
        keywords: "帮助 手册 faq 指南 说明 教程",
        badge: "W7.4",
        icon: BookOpen,
      },
    ];

    if (isCoachOrOwner || isSuperAdmin) {
      list.push(
        {
          id: "leader-captain",
          group: "leader",
          label: "团长运营驾驶舱",
          desc: "全团达标率圆环 · 未绑表激活漏斗 · 6位邀请码 · 成员花名册",
          href: "/dashboard/team?tab=president",
          keywords: "团长 驾驶舱 运营 激活 邀请码 花名册",
          badge: "W3.1",
          icon: Crown,
        },
        {
          id: "leader-report",
          group: "leader",
          label: "跑团周报 / 月报三视图工坊",
          desc: "长图海报 · 全员达标明细表 CSV · 微信群接龙纯文本一键复制",
          href: "/dashboard/team?tab=president&open=club-report",
          keywords: "周报 月报 战报 跑团 接龙 导出",
          badge: "W3.4",
          icon: BarChart3,
        },
        {
          id: "leader-compass",
          group: "leader",
          label: "教练全队体能信号灯罗盘 & 选兔雷达",
          desc: "红黄绿灰风险筛查 · TSB过载置顶 · 选兔稳健度雷达 · 批量派课",
          href: "/dashboard/team-coach?tab=coach",
          keywords: "教练 信号灯 罗盘 tsb 选兔 雷达 排课",
          badge: "W4.1",
          icon: ClipboardCheck,
        },
        {
          id: "leader-critique",
          group: "leader",
          label: "教练 5 秒连续批阅三栏舱",
          desc: "异常置顶队列 · 心率配速与生理对照 · 快捷词条连发 ⏎ 自动切下一位",
          href: "/dashboard/team-coach?mode=batch-critique",
          keywords: "批阅 点评 连续 5秒 教练 三栏",
          badge: "W4.2",
          icon: Sparkles,
        }
      );
    }

    if (hasManagedOrg || isSuperAdmin) {
      list.push(
        {
          id: "admin-org-audit",
          group: "admin",
          label: "大群 14 天实名准入核验台",
          desc: "AES-256 脱敏花名册审核 · 确认转正与超期解冻 · 保险名单导出",
          href: hasManagedOrg ? "/dashboard/team?org_action=audit" : "/dashboard/admin?tab=orgs",
          keywords: "大群 实名 核验 复旦戈 花名册 转正 解冻",
          badge: "W5.1",
          icon: Shield,
        },
        {
          id: "admin-orgs",
          group: "admin",
          label: "超管：大群与分团治理拓扑树",
          desc: "新建/编辑大群与跑团 · 指派团长 · 挂载分团 · 防误删二次核验",
          href: "/dashboard/admin?tab=orgs",
          keywords: "超管 大群 分团 跑团 拓扑 删除 crud",
          badge: "W5.2",
          icon: Shield,
        },
        {
          id: "admin-unaffiliated",
          group: "admin",
          label: "超管：自由跑者待引导池",
          desc: "筛选活跃未入团跑者 · 一键发送周边跑团入团引导",
          href: "/dashboard/admin?tab=unaffiliated",
          keywords: "超管 自由 跑者 未入团 引导",
          badge: "W5.2",
          icon: Users,
        },
        {
          id: "admin-analytics",
          group: "admin",
          label: "超管：全站增长漏斗与遥测大盘",
          desc: "小程序/Web双端 DAU · 激活转化漏斗 · 单跑者全生命周期轨迹钻取",
          href: "/dashboard/admin?tab=analytics",
          keywords: "超管 增长 漏斗 遥测 dau analytics",
          badge: "W5.3",
          icon: BarChart3,
        },
        {
          id: "admin-support",
          group: "admin",
          label: "超管：设备同步与 AI 运维排障",
          desc: "佳明双区/高驰健康监控 · Canova AI 引擎 · 反馈工单与秒修",
          href: "/dashboard/admin?tab=support",
          keywords: "超管 运维 排障 工单 garmin coros",
          badge: "W5.4",
          icon: Wrench,
        }
      );
    }

    list.push(
      {
        id: "act-theme",
        group: "actions",
        label: themeMode === "dark" ? "切换至 Volt Light v3.0 竞技亮色" : "切换至 Obsidian Dark 曜石暗黑",
        desc: "双色系 60-30-10 语义令牌即时切换 · 全站持久化记忆",
        keywords: "主题 颜色 暗黑 亮色 明亮 深色 theme light dark",
        badge: themeMode === "dark" ? "☀️ 亮色" : "🌙 暗黑",
        icon: themeMode === "dark" ? Sun : Moon,
        action: () => {
          onToggleTheme();
          onClose();
        },
      },
      {
        id: "act-coach",
        group: "actions",
        label: "呼出 Canova AI 教练实时对话舱",
        desc: "三支柱实时上下文（训练情况 / 训练计划 / 身体反应）一键调课",
        keywords: "ai 教练 对话 canova 调课 询问",
        badge: "AI",
        icon: Sparkles,
        action: () => {
          onClose();
          if (typeof window !== "undefined") {
            window.dispatchEvent(new CustomEvent("rgm-open-coach-chat"));
          }
        },
      }
    );

    return list;
  }, [isCoachOrOwner, isSuperAdmin, hasManagedOrg, themeMode, onToggleTheme, onClose]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (it) =>
        it.label.toLowerCase().includes(q) ||
        it.desc.toLowerCase().includes(q) ||
        it.keywords.toLowerCase().includes(q) ||
        (it.badge || "").toLowerCase().includes(q)
    );
  }, [items, query]);

  const grouped = useMemo(() => {
    const map = new Map<CommandPaletteItem["group"], CommandPaletteItem[]>();
    for (const item of filtered) {
      const arr = map.get(item.group) || [];
      arr.push(item);
      map.set(item.group, arr);
    }
    return Array.from(map.entries());
  }, [filtered]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => {
    if (selectedIndex >= filtered.length) {
      setSelectedIndex(0);
    }
  }, [filtered.length, selectedIndex]);

  function triggerItem(item: CommandPaletteItem) {
    if (item.action) {
      item.action();
      return;
    }
    if (item.href) {
      dispatchRgmNavIntent(item.href);
      router.push(item.href);
      onClose();
    }
  }

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        if (filtered.length > 0) setSelectedIndex((prev) => (prev + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (filtered.length > 0) setSelectedIndex((prev) => (prev - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        triggerItem(filtered[selectedIndex]);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, filtered, selectedIndex]);

  if (!open) return null;

  let flatIdx = -1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="全局指令与快速跳转"
      className="fixed inset-0 z-[99990] bg-black/65 backdrop-blur-sm flex items-start justify-center pt-[10vh] px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl bg-[var(--rgm-card)] border border-[var(--rgm-border)] shadow-2xl overflow-hidden flex flex-col max-h-[75vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Header */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[var(--rgm-border)]">
          <Search className="w-4 h-4 text-[#FC4C02] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="搜索跑者页面、教练批阅、选兔雷达、超管运维或切换主题..."
            className="flex-1 bg-transparent text-sm text-[var(--rgm-text)] placeholder:text-[var(--rgm-text-muted)] outline-none"
          />
          <kbd className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-[var(--rgm-card-3)] border border-[var(--rgm-border)] text-[10px] font-bold text-[var(--rgm-text-muted)]">
            ESC
          </kbd>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭搜索面板"
            className="p-1 rounded-lg text-[var(--rgm-text-muted)] hover:text-[var(--rgm-text)] transition cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Grouped Command Results */}
        <div className="overflow-y-auto p-2.5 space-y-3">
          {filtered.length === 0 ? (
            <div className="py-10 text-center text-xs text-[var(--rgm-text-muted)]">
              未找到匹配的页面或指令，试试“课表”、“批阅”、“选兔”、“隐私”或“亮色”
            </div>
          ) : (
            grouped.map(([groupKey, groupItems]) => (
              <div key={groupKey} className="space-y-1">
                <div className="px-2.5 pt-1 text-[10px] font-extrabold tracking-wider uppercase text-[var(--rgm-text-muted)]">
                  {GROUP_LABELS[groupKey]}
                </div>
                {groupItems.map((item) => {
                  flatIdx += 1;
                  const idx = flatIdx;
                  const isSel = idx === selectedIndex;
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onMouseEnter={() => setSelectedIndex(idx)}
                      onClick={() => triggerItem(item)}
                      className={`w-full text-left px-3 py-2.5 rounded-xl border transition flex items-center justify-between gap-3 cursor-pointer ${
                        isSel
                          ? "bg-[var(--rgm-brand-tint)] border-[#FC4C02]/45"
                          : "bg-transparent border-transparent hover:bg-[var(--rgm-card-2)]"
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border ${
                            isSel
                              ? "bg-[#FC4C02] text-white border-[#FC4C02]"
                              : "bg-[var(--rgm-card-2)] text-[var(--rgm-text-2)] border-[var(--rgm-border)]"
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs sm:text-sm font-bold text-[var(--rgm-text)] truncate">
                            {item.label}
                          </div>
                          <div className="text-[11px] text-[var(--rgm-text-muted)] truncate">
                            {item.desc}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {item.badge && (
                          <span className="px-2 py-0.5 rounded-md bg-[var(--rgm-card-3)] border border-[var(--rgm-border)] text-[10px] font-bold text-[var(--rgm-text-2)]">
                            {item.badge}
                          </span>
                        )}
                        {isSel && <CornerDownLeft className="w-3.5 h-3.5 text-[#FC4C02]" />}
                      </div>
                    </button>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer Hints */}
        <div className="px-4 py-2.5 border-t border-[var(--rgm-border)] bg-[var(--rgm-card-2)] flex items-center justify-between text-[11px] text-[var(--rgm-text-muted)]">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <Command className="w-3 h-3" />K 打开指令栏
            </span>
            <span>↑↓ 切换 · Enter 直达</span>
          </div>
          <span>RGM Web 3.0 角色自适应引擎</span>
        </div>
      </div>
    </div>
  );
}
