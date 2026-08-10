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
    const backendUrl = isDev 
      ? (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000')
      : (process.env.NEXT_PUBLIC_BACKEND_URL || 'https://rgm-backend-598386316625.asia-east1.run.app');
      
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
