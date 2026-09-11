import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 180000,
  expect: { timeout: 20000 },
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.FRONTEND_URL || "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    launchOptions: { args: ["--enable-unsafe-swiftshader"] },
  },
  reporter: [["list"], ["html", { open: "never" }]],
});
