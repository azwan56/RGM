"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { auth } from "@/lib/firebase";
import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";
import StravaConnectBtn from "@/components/StravaConnectBtn";

export default function Home() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [authLoading, setAuthLoading] = useState(true);

  useEffect(() => {
    return auth.onAuthStateChanged((u) => {
      setUser(u);
      setAuthLoading(false);
    });
  }, []);

  const handleGoogleLogin = async () => {
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
      router.push("/dashboard");
    } catch (error) {
      console.error("Login failed", error);
    }
  };

  // If already logged in, show a shortcut to dashboard
  const isLoggedIn = !!user;

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden relative">
      {/* Background aesthetic blobs */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-[#FC4C02]/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-600/10 blur-[150px] pointer-events-none" />

      <main className="max-w-7xl mx-auto px-6 pt-32 pb-20 relative z-10 text-center flex flex-col items-center justify-center min-h-screen">
        
        <div className="mb-8 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-sm font-medium text-zinc-300">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          Running Community Manager
        </div>

        <h1 className="text-6xl md:text-8xl font-black mb-6 tracking-tight">
          Track. <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#FC4C02] to-orange-400">Compete.</span> Evolve.
        </h1>
        
        <p className="text-zinc-400 text-lg md:text-xl max-w-2xl mx-auto mb-12 font-light leading-relaxed">
          The ultimate platform for your running community. Sync your Strava activities automatically, 
          compete on leaderboards, and get AI-driven coaching suggestions straight to your dashboard.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4">
          {authLoading ? (
            <div className="w-48 h-12 bg-white/5 rounded-xl animate-pulse" />
          ) : isLoggedIn ? (
            <>
              <button
                onClick={() => router.push("/dashboard")}
                className="px-8 py-3 bg-gradient-to-r from-[#FC4C02] to-orange-500 text-white font-bold rounded-xl transition-all hover:shadow-lg hover:shadow-[#FC4C02]/30 w-full sm:w-auto flex items-center justify-center gap-2"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                进入 Dashboard
              </button>
              <StravaConnectBtn />
            </>
          ) : (
            <>
              <button
                onClick={handleGoogleLogin}
                className="px-8 py-3 bg-white text-black font-bold rounded-xl transition-all hover:bg-zinc-100 hover:shadow-lg hover:shadow-white/10 w-full sm:w-auto flex items-center justify-center gap-3"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                使用 Google 登录
              </button>
              <StravaConnectBtn />
            </>
          )}

          <button
            onClick={() => router.push("/leaderboard")}
            className="px-6 py-3 bg-white/5 border border-white/10 hover:bg-white/10 text-white font-semibold rounded-xl transition-all w-full sm:w-auto"
          >
            View Leaderboard
          </button>
        </div>

        {/* Logged-in user status strip */}
        {isLoggedIn && (
          <div className="mt-6 flex items-center gap-3 text-sm text-zinc-500">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            已登录：{user.email}
            <button
              onClick={() => auth.signOut()}
              className="text-zinc-600 hover:text-red-400 transition-colors underline underline-offset-2"
            >
              登出
            </button>
          </div>
        )}

        <div className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto w-full text-left">
          {/* Card 1 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm">
            <h3 className="text-xl font-bold mb-2 text-white">Auto Sync</h3>
            <p className="text-zinc-400 text-sm">Connect once, and we'll automatically sync your runs, pace, and heart rate directly from Strava.</p>
          </div>
          {/* Card 2 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-[#FC4C02]/20 rounded-full blur-2xl"></div>
            <h3 className="text-xl font-bold mb-2 text-white relative z-10">Smart Goals</h3>
            <p className="text-zinc-400 text-sm relative z-10">Set weekly or monthly distance goals and track your completion percentage against your peers.</p>
          </div>
          {/* Card 3 */}
          <div className="bg-white/5 border border-white/10 p-6 rounded-2xl backdrop-blur-sm">
            <h3 className="text-xl font-bold mb-2 text-white">AI Analysis</h3>
            <p className="text-zinc-400 text-sm">Get intelligent feedback on your pacing, heart rate zones, and recovery suggestions powered by AI.</p>
          </div>
        </div>

      </main>
    </div>
  );
}
