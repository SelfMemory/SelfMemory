import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Kratos's default return URL is the old dashboard's /dashboard.
  redirects: async () => [{ source: "/dashboard/:path*", destination: "/wiki", permanent: false }],
};

export default nextConfig;
