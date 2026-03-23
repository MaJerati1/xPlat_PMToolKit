/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Increase proxy timeout for long-running LLM analysis calls
  experimental: {
    proxyTimeout: 300000, // 5 minutes in milliseconds
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/api/:path*',
      },
      {
        source: '/health/:path*',
        destination: 'http://backend:8000/health/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
