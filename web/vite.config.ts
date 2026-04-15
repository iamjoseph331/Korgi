import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/run": "http://127.0.0.1:8000",
      "/api": {
        target: "http://127.0.0.1:8000",
        // SSE: don't buffer
        ws: false,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
