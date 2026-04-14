"use client";

import React from 'react';

export default function StravaConnectBtn() {
    const handleConnect = () => {
        const clientId = process.env.NEXT_PUBLIC_STRAVA_CLIENT_ID;
        const redirectUri = `${process.env.NEXT_PUBLIC_BASE_URL}/auth/strava-callback`;
        const url = `https://www.strava.com/oauth/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&approval_prompt=force&scope=activity:read_all`;
        window.location.href = url;
    };

    return (
        <button 
            onClick={handleConnect}
            className="flex items-center justify-center gap-2 px-6 py-3 bg-[#FC4C02] text-white font-bold rounded-xl shadow-lg hover:bg-[#E34402] hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all w-full md:w-auto"
        >
            <svg viewBox="0 0 16 16" fill="currentColor" className="w-5 h-5">
                <path d="M10.573 5.376L11.9 2.827l4.086 8.24h-2.652l-1.434-2.898-1.434 2.898H7.814l2.759-5.691zm-4.49 2.755l-1.435 2.898H1.996l2.652-5.358 2.652 5.358H4.648L3.213 8.131h2.87z" />
            </svg>
            连接 Strava
        </button>
    );
}
