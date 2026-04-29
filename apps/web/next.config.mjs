/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  typedRoutes: false,
  output: "standalone",
  distDir: process.env.NEXT_DIST_DIR || ".next"
};

export default nextConfig;
