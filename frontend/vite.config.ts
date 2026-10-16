import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Proxy ke Django agar browser melihat satu origin: cookie sesi dan CSRF bekerja tanpa CORS.
// changeOrigin sengaja tidak diaktifkan: header Host asli dipertahankan (cocok dengan Origin
// untuk pemeriksaan CSRF Django).
const apiTarget = process.env.VITE_API_PROXY ?? "http://localhost:8000";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Hanya diisi untuk E2E di jaringan Docker (mis. VITE_ALLOWED_HOSTS=snr-e2e-front).
    allowedHosts: process.env.VITE_ALLOWED_HOSTS?.split(",").filter(Boolean),
    proxy: {
      "/api": { target: apiTarget, changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
  },
});
