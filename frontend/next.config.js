/** @type {import('next').NextConfig} */
const nextConfig = {
  // Hide the Next.js development indicator in the desktop development window.
  devIndicators: false,
  // Allow images from local filesystem served via the FastAPI backend
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "127.0.0.1", port: "8000" },
      { protocol: "http", hostname: "localhost", port: "8000" },
    ],
  },
  // In production/Tauri we export as static files
  output: process.env.NEXT_EXPORT === "1" ? "export" : undefined,
};

module.exports = nextConfig;
