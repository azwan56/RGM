import type { Metadata } from "next";
import "./globals.css";
import FirebaseAuth from "@/components/FirebaseAuth";

export const metadata: Metadata = {
  title: "RGM · 跑团管理平台",
  description: "跑团数据同步、AI 教练分析、团队挑战排行榜 — 跑者的一站式社区管理平台。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased bg-[#0a0a0a] min-h-screen flex flex-col font-sans">
        <nav className="w-full absolute top-0 z-50 p-6 flex justify-between items-center max-w-7xl mx-auto left-0 right-0 pointer-events-none">
          <div className="text-white font-bold text-xl tracking-tight pointer-events-auto">RGM<span className="text-[#FC4C02]">.</span></div>
          <div className="pointer-events-auto">
            <FirebaseAuth />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
