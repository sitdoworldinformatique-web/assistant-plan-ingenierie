import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const cible = process.env.API_CIBLE ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": cible } },
  build: { target: "es2020", sourcemap: false },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
