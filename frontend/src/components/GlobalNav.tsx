"use client";

import { usePathname } from "next/navigation";
import FirebaseAuth from "./FirebaseAuth";

/**
 * Global navigation bar — shows RGM logo + auth on non-dashboard pages.
 * Dashboard pages have their own dedicated headers, so we hide this to
 * prevent overlapping buttons (e.g. "保存档案" vs "退出").
 */
export default function GlobalNav() {
  const pathname = usePathname();

  // Hide on profile page — it has its own sticky header with save button
  if (pathname.startsWith("/dashboard/profile")) return null;

  return (
    <nav className="w-full absolute top-0 z-50 p-4 md:p-6 flex justify-between items-center max-w-7xl mx-auto left-0 right-0 pointer-events-none">
      <div className="text-white font-bold text-lg md:text-xl tracking-tight pointer-events-auto">
        RGM<span className="text-[#FC4C02]">.</span>
      </div>
      <div className="pointer-events-auto">
        <FirebaseAuth />
      </div>
    </nav>
  );
}
