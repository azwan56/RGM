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
  const [status, setStatus] = useState('Verifying with Strava...');
  // Guard: prevent onAuthStateChanged from firing the exchange request more than once
  const hasCalled = useRef(false);

  useEffect(() => {
    if (error) {
      setStatus('Access denied. You must authorize Strava to continue.');
      return;
    }

    const unsubscribe = auth.onAuthStateChanged(async (user) => {
      if (!user) {
        setStatus("You must be logged in to this App first before connecting Strava.");
        return;
      }

      // Prevent double-firing (onAuthStateChanged can emit multiple times)
      if (hasCalled.current) return;
      hasCalled.current = true;

      if (code) {
        try {
          const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

          // 1. Exchange Strava OAuth code for tokens and persist to Firestore
          await axios.post(`${backendUrl}/api/auth/strava`, {
            code: code,
            uid: user.uid,
          });

          // 2. Auto-trigger an initial Strava sync so the dashboard is not empty
          setStatus('Connected! Syncing your Strava data...');
          try {
            await axios.post(`${backendUrl}/api/sync/trigger`, { uid: user.uid });
          } catch (syncErr) {
            // Non-fatal — user can always manually sync from the dashboard
            console.warn('Initial sync failed (non-fatal):', syncErr);
          }

          setStatus('All done! Redirecting to Dashboard...');
          setTimeout(() => router.push('/dashboard'), 1500);
        } catch (err) {
          console.error(err);
          setStatus('Failed to connect Strava. Please try again.');
        }
      }
    });

    return () => unsubscribe();
  }, [code, error, router]);

  return (
    <div className="bg-zinc-800/80 backdrop-blur-md border border-zinc-700/50 p-8 rounded-2xl shadow-2xl text-center max-w-sm w-full mx-4">
      <div className="w-16 h-16 border-4 border-[#FC4C02] border-t-transparent rounded-full animate-spin mx-auto mb-6"></div>
      <h2 className="text-xl font-medium text-white">{status}</h2>
    </div>
  );
}

export default function StravaCallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(252,76,2,0.15),rgba(255,255,255,0))]">
      <Suspense fallback={<div className="text-white">Loading...</div>}>
        <CallbackContent />
      </Suspense>
    </div>
  );
}
