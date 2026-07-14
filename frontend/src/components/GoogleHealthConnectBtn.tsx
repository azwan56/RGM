"use client";

import React from 'react';

export default function GoogleHealthConnectBtn() {
    const handleConnect = () => {
        const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "598386316625-v59007b4.apps.googleusercontent.com"; // Fallback placeholder
        const redirectUri = `${window.location.origin}/auth/google-health-callback`;
        const scope = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly https://www.googleapis.com/auth/googlehealth.sleep.readonly email profile openid";
        const url = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent`;
        window.location.href = url;
    };

    return (
        <button 
            onClick={handleConnect}
            className="flex items-center gap-2.5 px-6 py-3 bg-gradient-to-r from-[#4285F4]/30 via-[#34A853]/10 to-[#FBBC05]/20 border border-white/10 hover:border-blue-500/50 text-white font-bold rounded-xl transition-all duration-300 hover:shadow-lg hover:shadow-blue-500/10 w-full sm:w-auto justify-center group"
            aria-label="Connect Google Health"
        >
            <svg className="w-5 h-5 transition-transform duration-300 group-hover:scale-110" viewBox="0 0 24 24">
                <path fill="#EA4335" d="M12 5.04c1.67 0 3.2.58 4.38 1.69l3.27-3.27C17.67 1.6 15.02 0 12 0 7.33 0 3.32 2.69 1.4 6.62l3.87 3C6.18 6.94 8.87 5.04 12 5.04z" />
                <path fill="#4285F4" d="M23.49 12.27c0-.82-.07-1.6-.2-2.38H12v4.51h6.44c-.28 1.47-1.11 2.71-2.36 3.55l3.66 2.84c2.14-1.97 3.37-4.88 3.37-8.52z" />
                <path fill="#FBBC05" d="M5.27 14.38c-.24-.71-.38-1.47-.38-2.26s.14-1.55.38-2.26L1.4 6.86C.51 8.65 0 10.66 0 12.78s.51 4.13 1.4 5.92l3.87-3.04z" />
                <path fill="#34A853" d="M12 24c3.24 0 5.97-1.07 7.96-2.91l-3.66-2.84c-1.01.68-2.31 1.09-3.96 1.09-3.13 0-5.82-2.1-6.77-4.93l-3.87 3C3.32 21.31 7.33 24 12 24z" />
            </svg>
            <span className="bg-gradient-to-r from-white to-zinc-300 bg-clip-text text-transparent group-hover:text-white transition-all">连接 Google Health / Fitbit</span>
        </button>
    );
}
