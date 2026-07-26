import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import https from "node:https";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
const createProxyOptions = () => ({
  target: apiProxyTarget,
  changeOrigin: true,
  ...(apiProxyTarget.startsWith("https:")
    ? { agent: new https.Agent({ family: 4, keepAlive: true }) }
    : {}),
});

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": createProxyOptions(),
      "/uploads": createProxyOptions(),
    },
  },
});
