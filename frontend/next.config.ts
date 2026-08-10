import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "**",
      },
    ],
  },
  async rewrites() {
    const isDev = process.env.NODE_ENV === 'development';
    let backendUrl = 'https://rgm-backend-598386316625.asia-east1.run.app';
    if (isDev) {
      backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    } else if (process.env.NEXT_PUBLIC_BACKEND_URL && !process.env.NEXT_PUBLIC_BACKEND_URL.includes('3v6u4behxa')) {
      backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    }
    backendUrl = backendUrl.replace(/\/$/, '');
      
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
