"use client";

import React from 'react';

export default function StravaConnectBtn() {
    const handleConnect = () => {
        const clientId = process.env.NEXT_PUBLIC_STRAVA_CLIENT_ID;
        const redirectUri = `${process.env.NEXT_PUBLIC_BASE_URL}/auth/strava-callback`;
        const url = `https://www.strava.com/oauth/authorize?client_id=${clientId}&response_type=code&redirect_uri=${redirectUri}&approval_prompt=force&scope=activity:read_all,profile:read_all`;
        window.location.href = url;
    };

    return (
        <button 
            onClick={handleConnect}
            className="flex items-center gap-2.5 px-6 py-3 bg-[#FC4C02] hover:bg-[#e04400] text-white font-bold rounded-xl transition-all hover:shadow-lg hover:shadow-[#FC4C02]/30 w-full sm:w-auto justify-center"
            aria-label="Connect with Strava"
        >
            {/* Strava logo mark */}
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169" />
            </svg>
            Connect with Strava
        </button>
    );
}
