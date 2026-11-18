import Link from "next/link";
import Navbar from "@/components/Navbar";
import { AlertTriangle, Home, Users } from "lucide-react";

export default function NotFoundPage() {
  return (
    <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] flex flex-col">
      <Navbar />
      <main className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-lg w-full rgm-bento-card p-8 text-center space-y-5">
          <div className="w-16 h-16 rounded-2xl bg-[var(--rgm-amber-tint)] border border-amber-500/35 text-amber-500 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <div className="space-y-2">
            <div className="text-xs font-black tracking-widest text-[#FC4C02] uppercase">
              404 · PAGE NOT FOUND
            </div>
            <h1 className="text-2xl font-black text-[var(--rgm-text)]">
              页面不存在或链接已失效
            </h1>
            <p className="text-xs sm:text-sm text-[var(--rgm-text-2)] leading-relaxed">
              该邀请链接可能已过期、跑团已解散或你暂时不再具备访问权限。可以返回个人工作台或跑团广场继续训练。
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#FC4C02] hover:bg-orange-600 text-white text-xs font-bold transition shadow-md shadow-[#FC4C02]/25"
            >
              <Home className="w-4 h-4" />
              返回跑者工作台
            </Link>
            <Link
              href="/dashboard/team"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--rgm-card-2)] border border-[var(--rgm-border)] text-[var(--rgm-text)] hover:border-[#FC4C02]/45 text-xs font-bold transition"
            >
              <Users className="w-4 h-4 text-[#FC4C02]" />
              浏览跑团广场
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
