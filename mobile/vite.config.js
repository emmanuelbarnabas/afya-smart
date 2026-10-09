// PWA ya Afya Smart USSD — app ndogo ya simu (mobile-only).
// Base /mobile/ ili backend ihudumie kwenye /mobile.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/mobile/",
  server: {
    port: 5175,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/ussd-config": { target: "http://localhost:8000", changeOrigin: true },
      "/mobile/sw.js": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // service worker lazima isafiri bila rewrite ya query
        rewrite: (p) => p,
      },
    },
  },
});
