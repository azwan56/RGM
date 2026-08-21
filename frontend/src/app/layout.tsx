import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RGM 跑团管理与 AI 智能教练平台 (国内版)",
  description: "基于阿里云与 Supabase，直连 Garmin 佳明数据，配备 Renato Canova 顶级马拉松 AI 教练与微信生态联动。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="antialiased bg-[#0a0a0a] text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}
