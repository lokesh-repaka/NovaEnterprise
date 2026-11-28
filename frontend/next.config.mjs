/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8001/api/:path*',
      },
      {
        source: '/health/:path*',
        destination: 'http://localhost:8001/health/:path*',
      },
    ];
  },
};

export default nextConfig;
