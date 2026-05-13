"use client";

import { usePathname, useRouter } from "next/navigation";

const NAV_ITEMS = [
  {
    key: "dashboard",
    href: "/dashboard",
    label: "首页",
    color: "orange",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1h-2z" />
      </svg>
    ),
  },
  {
    key: "analysis",
    href: "/dashboard/analysis",
    label: "深度分析",
    color: "blue",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    key: "coach",
    href: "/dashboard/coach",
    label: "AI教练",
    color: "emerald",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
  },
  {
    key: "team",
    href: "/dashboard/team",
    label: "我的团队",
    color: "zinc",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
  },
  {
    key: "profile",
    href: "/dashboard/profile",
    label: "我的档案",
    color: "orange",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
        <circle cx="12" cy="8" r="4"/>
        <path strokeLinecap="round" d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
      </svg>
    ),
  },
];

const COLOR_MAP: Record<string, { bg: string; bgActive: string; border: string; borderActive: string; text: string; textActive: string }> = {
  orange:  { bg: "bg-[#FC4C02]/10", bgActive: "bg-[#FC4C02]/25", border: "border-[#FC4C02]/20", borderActive: "border-[#FC4C02]/50", text: "text-zinc-500", textActive: "text-[#FC4C02]" },
  blue:    { bg: "bg-blue-500/10",   bgActive: "bg-blue-500/25",   border: "border-blue-500/20",   borderActive: "border-blue-400/50",   text: "text-zinc-500", textActive: "text-blue-400" },
  emerald: { bg: "bg-emerald-500/10", bgActive: "bg-emerald-500/25", border: "border-emerald-500/20", borderActive: "border-emerald-400/50", text: "text-zinc-500", textActive: "text-emerald-400" },
  zinc:    { bg: "bg-white/5",       bgActive: "bg-white/15",      border: "border-white/10",      borderActive: "border-white/30",      text: "text-zinc-500", textActive: "text-white" },
};

export default function PageNav() {
  const pathname = usePathname();
  const router = useRouter();

  // Determine which item is active
  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  return (
    <nav className="flex items-center gap-1.5 sm:gap-2">
      {NAV_ITEMS.map((item) => {
        const active = isActive(item.href);
        const c = COLOR_MAP[item.color];

        return (
          <button
            key={item.key}
            onClick={() => router.push(item.href)}
            className={`flex-shrink-0 flex flex-col items-center gap-0.5 group transition-all ${
              active ? "scale-105" : "hover:scale-105"
            }`}
            title={item.label}
          >
            <div
              className={`w-10 h-10 sm:w-11 sm:h-11 rounded-xl sm:rounded-2xl flex items-center justify-center transition-all ${
                active
                  ? `${c.bgActive} ${c.borderActive} border-2 shadow-lg`
                  : `${c.bg} ${c.border} border hover:bg-opacity-25`
              }`}
            >
              <span className={active ? c.textActive : `${c.text} group-hover:${c.textActive}`}>
                {item.icon}
              </span>
            </div>
            <span
              className={`text-[9px] sm:text-[10px] font-medium transition-colors ${
                active ? c.textActive : `text-zinc-600 group-hover:text-zinc-400`
              }`}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
