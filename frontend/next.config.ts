import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "rgm.vanpower.net" },
      { protocol: "https", hostname: "*.vanpower.net" },
      { protocol: "https", hostname: "thirdwx.qlogo.cn" },
      { protocol: "https", hostname: "wx.qlogo.cn" },
      { protocol: "http", hostname: "127.0.0.1" },
      { protocol: "http", hostname: "localhost" },
    ],
  },
  async rewrites() {
    if (process.env.NODE_ENV === "production") {
      return [];
    }
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/privacy",
        destination: `${backendUrl}/privacy`,
      },
      {
        source: "/citations",
        destination: `${backendUrl}/citations`,
      },
    ];
  },
};

export default nextConfig;
