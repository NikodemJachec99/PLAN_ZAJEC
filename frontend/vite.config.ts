import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs on :8000 (uvicorn); same-origin /api calls are proxied there,
// exactly like nginx does in production.
const apiTarget = process.env.VITE_DEV_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
  preview: {
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
