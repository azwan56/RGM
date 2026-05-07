import type { Metadata, Viewport } from "next";
import "./globals.css";
import GlobalNav from "@/components/GlobalNav";

export const metadata: Metadata = {
  title: "RGM · 跑团管理平台",
  description: "跑团数据同步、AI 教练分析、团队挑战排行榜 — 跑者的一站式社区管理平台。",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "RGM",
  },
  icons: {
    icon: "/icons/icon-192x192.png",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#FC4C02",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased bg-[#0a0a0a] min-h-screen flex flex-col font-sans">
        <GlobalNav />
        {children}
      </body>
    </html>
  );
}
