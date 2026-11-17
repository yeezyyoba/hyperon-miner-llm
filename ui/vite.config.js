import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the FastAPI server runs on :8000 (make api); Vite proxies /api to it.
// In production FastAPI serves the built files from ui/dist (make ui).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: false } },
  },
});
