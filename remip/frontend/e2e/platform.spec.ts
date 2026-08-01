import { expect, test } from "@playwright/test";

const DEMO_EMAIL = "demo@example.com";
const DEMO_PASSWORD = "demo1234";
const ADMIN_EMAIL = "admin@example.com";

test("landing page shows product and demo-data badge", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("mercato immobiliare");
  await expect(page.getByText("Dati demo").first()).toBeVisible();
});

test("login and see the zone dashboard with KPIs and forecasts", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Accedi" }).click();
  await page.waitForURL("**/dashboard");

  await expect(page.getByText("Prezzo medio").first()).toBeVisible();
  await expect(page.getByText("€/m² medio").first()).toBeVisible();
  await expect(page.getByText("Previsioni", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("scenario strutturale").first()).toBeVisible();
  // transparency block
  await expect(page.getByText("Fonte: demo_it", { exact: false }).first()).toBeVisible();
});

test("search listings, open a detail page with history", async ({ page }) => {
  await page.goto("/listings");
  await expect(page.getByText(/annunci trovati/)).toBeVisible();
  const firstCard = page.locator("a[href^='/listings/']").first();
  await firstCard.click();
  await expect(page.getByRole("heading", { name: "Cronologia dell'annuncio" })).toBeVisible();
  await expect(page.getByText("Storico prezzi")).toBeVisible();
  await expect(page.getByText("Prima rilevazione dell'annuncio").first()).toBeVisible();
});

test("register, onboard, add a listing to the watchlist", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("Nome completo").fill("Utente E2E");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel(/Password/).fill("password123");
  await page.getByRole("button", { name: "Registrati" }).click();

  await page.waitForURL("**/onboarding");
  await page.getByRole("radio", { name: /Investire/ }).click();
  await page.getByRole("button", { name: "Continua" }).click();
  await page.waitForURL("**/dashboard");

  await page.goto("/listings");
  await page.locator("a[href^='/listings/']").first().click();
  await page.getByRole("button", { name: /Aggiungi alla watchlist/ }).click();
  await expect(page.getByText("Aggiunto alla watchlist ✓")).toBeVisible();

  await page.goto("/watchlist");
  await expect(page.getByRole("link", { name: "Annuncio osservato" })).toBeVisible();
});

test("select two listings and compare them side by side", async ({ page }) => {
  await page.goto("/listings");
  await expect(page.getByText(/annunci trovati/)).toBeVisible();
  const compareButtons = page.getByRole("button", { name: /Confronta \(max/ });
  await compareButtons.nth(0).click();
  await compareButtons.nth(1).click();

  await page.goto("/compare");
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("Scostamento vs zona")).toBeVisible();
});

test("dashboard shows the trend explanation and an area comparison", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("Prezzo medio").first()).toBeVisible();
  await expect(page.getByText(/Perché il mercato è|Servono almeno/).first()).toBeVisible();

  await expect(page.getByRole("heading", { name: "Confronta con altre zone" })).toBeVisible();
  const pickers = page.getByLabel("Città");
  await pickers.nth(1).selectOption({ index: 1 });
  await page.getByRole("button", { name: /Confronta .* con le zone selezionate/ }).click();
  await expect(page.getByRole("columnheader", { name: "€/m² medio" })).toBeVisible();
});

test("mute a notification type in preferences", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Accedi" }).click();
  await page.waitForURL("**/dashboard");

  await page.goto("/notifications");
  await page.getByRole("button", { name: /Prezzo ridotto/ }).click();
  await expect(page.getByText("Preferenze salvate ✓")).toBeVisible();
});

test("admin can see the admin panel and toggle a data source", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Accedi" }).click();
  await page.waitForURL("**/dashboard");

  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "Pannello amministratore" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /^Utenti/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Fonti dati" })).toBeVisible();
});

test("non-admin is denied access to the admin panel", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(DEMO_EMAIL);
  await page.getByLabel("Password").fill(DEMO_PASSWORD);
  await page.getByRole("button", { name: "Accedi" }).click();
  await page.waitForURL("**/dashboard");

  await page.goto("/admin");
  await expect(page.getByText("Accesso riservato agli amministratori.")).toBeVisible();
});
