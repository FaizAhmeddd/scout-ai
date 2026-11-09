import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Same-origin in development: API calls and generated media both go through the dev server.
    proxy: {
      "/api": API,
      "/outputs": API,
    },
  },
});
