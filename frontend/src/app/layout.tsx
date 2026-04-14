import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import FirebaseAuth from "@/components/FirebaseAuth";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Running Community Manager",
  description: "The ultimate platform for your running community. Sync Strava activities, compete on leaderboards, and get AI-driven coaching insights.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[#0a0a0a] min-h-screen flex flex-col`}>
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
