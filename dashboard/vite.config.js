import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev proxy: /api → backend ya FastAPI (epuka CORS wakati wa dev)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ussd-config": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
