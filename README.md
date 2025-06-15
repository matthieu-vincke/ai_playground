agent-ui

Install with npx create-agent-ui@latest

Then modify the next.config.js file to allow the playground to connect to the agent-ui

// next.config.js or next.config.ts
/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  experimental: {
  },
  
  allowedDevOrigins: [
    '*.codeanywhere.com', '3000-matthieu-vincke-ai-playg-smxa860a89.app.codeanywhere.com'
  ]
}

export default nextConfig

Then run it

cd agent-ui && npm run dev


playground settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)