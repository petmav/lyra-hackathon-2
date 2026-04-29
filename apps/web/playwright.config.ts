import { defineConfig, devices } from "@playwright/test";

const useExistingServer = process.env.PRAETOR_E2E_USE_EXISTING_SERVER === "1";
const baseURL = process.env.PRAETOR_E2E_WEB_BASE ?? (useExistingServer ? "http://localhost:3000" : "http://localhost:3100");

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  reporter: [["list"], ["html", { outputFolder: "../../screenshots/playwright-report", open: "never" }]],
  outputDir: "../../screenshots/playwright-artifacts",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  webServer: useExistingServer
    ? undefined
    : {
        command: "npx next dev -p 3100",
        url: baseURL,
        reuseExistingServer: false,
        timeout: 120_000,
        env: {
          NEXT_PUBLIC_DATA_SOURCE: process.env.NEXT_PUBLIC_DATA_SOURCE ?? "fixtures",
          NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000",
          NEXT_PUBLIC_API_TOKEN: process.env.NEXT_PUBLIC_API_TOKEN ?? "dev"
        }
      },
  projects: [
    {
      name: "chromium-desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1100 } }
    },
    {
      name: "chromium-mobile",
      use: { ...devices["Pixel 7"] }
    }
  ]
});
