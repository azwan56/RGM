"use client";
import { useState, useEffect } from "react";
import { auth } from "@/lib/firebase";
import { GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";

export default function FirebaseAuth() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return auth.onAuthStateChanged((u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  const login = async () => {
    try {
      const provider = new GoogleAuthProvider();
      await signInWithPopup(auth, provider);
    } catch (error) {
      console.error("Login failed", error);
    }
  };

  if (loading) return <div className="w-24 h-8 animate-pulse bg-white/5 rounded-lg"></div>;

  if (user) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-zinc-300 text-sm hidden md:inline-block">{user.email}</span>
        <button onClick={() => signOut(auth)} className="text-sm font-medium text-zinc-400 hover:text-red-400 transition-colors">
          退出
        </button>
      </div>
    );
  }

  return (
    <button onClick={login} className="px-5 py-2 bg-white text-black text-sm font-semibold rounded-full hover:bg-zinc-200 shadow-lg shadow-white/10 transition-all">
      登录
    </button>
  );
}
