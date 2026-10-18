import { defineConfig, devices } from "@playwright/test";

// Parcours de bout en bout : API (SQLite jetable, sans clé IA) + interface Vite.
const PORT_API = 8010;
const PORT_WEB = 5180;
const python = process.env.E2E_PYTHON ?? "python3";
const base = `sqlite:///${process.env.E2E_DB ?? `/tmp/assistant-e2e-${Date.now()}.db`}`;

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT_WEB}`, locale: "fr-FR", trace: "retain-on-failure" },
  projects: [
    { name: "bureau", use: { ...devices["Desktop Chrome"] } },
    { name: "telephone", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT_API}`,
      cwd: "../2-backend",
      url: `http://127.0.0.1:${PORT_API}/api/sante`,
      env: {
        PYTHONPATH: ".:../3-connecteurs-deploiement/connecteurs",
        DATABASE_URL: base,
        ANTHROPIC_API_KEY: "",
        GEMINI_API_KEY: "",
        ADMIN_EMAIL: "admin-e2e@exemple.cd",
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${PORT_WEB} --strictPort`,
      url: `http://127.0.0.1:${PORT_WEB}`,
      env: { API_CIBLE: `http://127.0.0.1:${PORT_API}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});
