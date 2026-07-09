/** @type {import('next').NextConfig} 
 * The main configuration file for Next.js
 * output: "standalone" tells Next.js to generate a smaller production server under .next/standalone/
 * Your Dockerfile can then copy this directory into the final production image.
*/
const nextConfig = {
  output: "standalone",
};

module.exports = nextConfig;
