import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

// Escape a string so it can be embedded literally in a RegExp.
function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export default defineConfig(({ mode }) => {
  // loadEnv merges .env files with matching process.env vars (prefix "" =
  // everything), so a build-time VITE_API_URL from either source is picked up.
  // Env dir "." resolves against Vite's project root (the frontend directory).
  const env = loadEnv(mode, ".", "");
  const apiUrl = env.VITE_API_URL || "http://localhost:8000";
  const apiOrigin = new URL(apiUrl).origin;

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: "autoUpdate",
        strategies: "generateSW",
        injectRegister: "auto",
        manifest: {
          name: "Portfolius",
          short_name: "Portfolius",
          description:
            "A private portfolio ledger for holdings, allocation, and what-if trades.",
          theme_color: "#faf8f2",
          background_color: "#faf8f2",
          display: "standalone",
          start_url: "/",
          icons: [
            {
              src: "/pwa-192x192.png",
              sizes: "192x192",
              type: "image/png",
              purpose: "any",
            },
            {
              src: "/pwa-512x512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "any",
            },
            {
              src: "/pwa-maskable-512x512.png",
              sizes: "512x512",
              type: "image/png",
              purpose: "maskable",
            },
            {
              src: "/pwa-maskable-192x192.png",
              sizes: "192x192",
              type: "image/png",
              purpose: "maskable",
            },
          ],
        },
        workbox: {
          navigateFallback: "index.html",
          // Defense-in-depth: navigateFallback only applies to navigation
          // requests, but this guarantees an API path can never be shadowed by
          // the SPA fallback.
          navigateFallbackDenylist: [/^\/api/],
          // Financial data (the API origin) and Supabase auth/session tokens
          // must never be served stale, so force both to bypass the cache
          // entirely. generateSW serializes this config and does not capture
          // closures, so the API origin is baked into an anchored RegExp
          // rather than matched via a function that closes over `apiOrigin`.
          runtimeCaching: [
            {
              urlPattern: new RegExp(`^${escapeRegExp(apiOrigin)}/`),
              handler: "NetworkOnly",
            },
            {
              urlPattern: /^https:\/\/[^/]+\.supabase\.co\//,
              handler: "NetworkOnly",
            },
          ],
        },
      }),
    ],
    server: {
      host: true,
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
    },
  };
});
