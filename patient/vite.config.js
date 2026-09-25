import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// App ya mgonjwa (client) — base /app/ ili backend ihudumie kwenye /app
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  server: {
    port: 5174,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/my-queue": { target: "http://localhost:8000", changeOrigin: true },
      "/ussd-config": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
