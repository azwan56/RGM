import type { Metadata, Viewport } from "next";
import "./globals.css";
import UiFeedbackProvider from "@/components/ui/UiFeedbackProvider";

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b0b0e" },
  ],
  colorScheme: "dark light",
};

export const metadata: Metadata = {
  title: "万跑跑团助手｜跑团管理与 Canova 科学耐力训练平台",
  description: "专为跑者与跑团打造的一站式管理与训练平台，支持佳明、高驰、苹果、华为、颂拓手表同步，配备 Renato Canova 马拉松专项教练与微信小程序实时互通。",
  referrer: "no-referrer",
  icons: {
    icon: "/logo.png",
    shortcut: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var m=localStorage.getItem('rgm_theme_mode');if(m==='light'){document.documentElement.classList.add('theme-light');}else{document.documentElement.classList.remove('theme-light');}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="antialiased min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)]">
        <UiFeedbackProvider>
          <div className="min-h-screen bg-[var(--rgm-bg)] text-[var(--rgm-text)] transition-colors duration-200">
            {children}
          </div>
        </UiFeedbackProvider>
      </body>
    </html>
  );
}
