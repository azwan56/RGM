"use client";
import { useState, useEffect } from "react";
import { auth } from "@/lib/firebase";
import { signOut } from "firebase/auth";
import AuthModal from "./AuthModal";

export default function FirebaseAuth() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    return auth.onAuthStateChanged((u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="w-24 h-8 animate-pulse bg-white/5 rounded-lg" />;
  }

  if (user) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-zinc-300 text-sm hidden md:inline-block truncate max-w-[180px]">
          {user.email || user.phoneNumber || "已登录"}
        </span>
        <button
          onClick={() => signOut(auth)}
          className="text-sm font-medium text-zinc-400 hover:text-red-400 transition-colors"
        >
          退出
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        onClick={() => setModalOpen(true)}
        className="px-5 py-2 bg-white text-black text-sm font-semibold rounded-full hover:bg-zinc-200 shadow-lg shadow-white/10 transition-all"
      >
        登录
      </button>
      <AuthModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
