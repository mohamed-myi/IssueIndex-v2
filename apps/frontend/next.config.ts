import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    reactStrictMode: true,
    output: "standalone",
    typedRoutes: true,
    turbopack: {}, // No turbopack config needed - webpack config is for production only
    webpack: (config, { dev }) => {
        if (!dev) {
            // Ensure mocks are never bundled in production builds
            // This prevents any accidental inclusion of mock data
            config.resolve.alias = {
                ...config.resolve.alias,
                "@/mocks": false,
            };
        }
        return config;
    },
};

export default nextConfig;
