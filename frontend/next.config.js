/** @type {import('next').NextConfig} 
 * The main configuration file for Next.js
 * output: "standalone" tells Next.js to generate a smaller production server under .next/standalone/
 * Your Dockerfile can then copy this directory into the final production image.
*/
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const apiProxyTarget = (
      process.env.INTERNAL_API_BASE_URL || "http://localhost:8000"
    ).replace(/\/$/, "");

    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
