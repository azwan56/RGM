"use client";

import { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { auth } from '@/lib/firebase';
import axios from '@/lib/apiClient';

function CallbackContent() {
  const searchParams = useSearchParams();
  const code = searchParams.get('code');
  const error = searchParams.get('error');
  const router = useRouter();
  const [status, setStatus] = useState('正在向 Google 验证权限...');
  const hasCalled = useRef(false);

  useEffect(() => {
    if (error) {
      setStatus('授权被拒绝。您必须允许 RGM 访问 Google Health 才能继续。');
      return;
    }

    const unsubscribe = auth.onAuthStateChanged(async (user) => {
      if (!user) {
        setStatus("请先登录 RGM 再关联 Google Health 账号。");
        return;
      }

      if (hasCalled.current) return;
      hasCalled.current = true;

      if (code) {
        try {
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
          const redirectUri = `${process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'}/auth/google-health-callback`;

          // 1. Exchange Google OAuth code for tokens and persist to Firestore
          setStatus('验证成功，正在保存 Google 授权令牌...');
          await axios.post(`${backendUrl}/api/google-health/connect`, {
            code: code,
            redirect_uri: redirectUri,
          });

          setStatus('连接成功！正在同步您的 Fitbit/Google Health 数据...');
          setStatus('数据同步完成！正在返回控制台...');
          setTimeout(() => router.push('/dashboard'), 1500);
        } catch (err) {
          console.error(err);
          setStatus('关联 Google Health 失败，请检查 GCP 授权配置后重试。');
        }
      }
    });

    return () => unsubscribe();
  }, [code, error, router]);

  return (
    <div className="bg-zinc-900/80 backdrop-blur-md border border-zinc-800 p-8 rounded-2xl shadow-2xl text-center max-w-sm w-full mx-4">
      <div className="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
      <h2 className="text-xl font-medium text-white">{status}</h2>
    </div>
  );
}

export default function GoogleHealthCallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(59,130,246,0.15),rgba(255,255,255,0))]">
      <Suspense fallback={<div className="text-white">加载中...</div>}>
        <CallbackContent />
      </Suspense>
    </div>
  );
}
