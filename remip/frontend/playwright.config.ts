import { defineConfig } from "@playwright/test";

// E2E: boots the real backend (fresh SQLite DB with full demo seed) and the
// built Next.js app, then drives Chromium against them.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    // Use the environment's preinstalled Chromium when available instead of
    // downloading a matching browser build.
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : undefined,
  },
  webServer: [
    {
      command:
        "cd ../backend && rm -f e2e.db && REMIP_DATABASE_URL=sqlite:///./e2e.db " +
        "REMIP_SECRET_KEY=e2e-secret-not-for-production-0123456789 " +
        "python3 -m uvicorn app.main:app --port 8000",
      url: "http://localhost:8000/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run start",
      url: "http://localhost:3000",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
