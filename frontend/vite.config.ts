import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// В разработке SPA на :5173 ходит в backend на :8000; WebSocket (IC-021) идёт тем же прокси.
// Origin остаётся http://localhost:5173: backend в APP_ENV=dev разрешает его (CLAUDE.md §9.3).
export default defineConfig({
  plugins: [react()],
  server: {
    // Именно localhost: backend в dev разрешает Origin `http://localhost:5173`, а не 127.0.0.1.
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
