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
            className="transition-transform hover:-translate-y-0.5 focus:outline-none flex items-center justify-center w-full md:w-auto"
            aria-label="Connect with Strava"
        >
            <img 
                src="/icons/btn_strava_connectwith_orange.svg" 
                alt="Connect with Strava" 
                className="w-[193px] h-[48px] object-contain"
            />
        </button>
    );
}
