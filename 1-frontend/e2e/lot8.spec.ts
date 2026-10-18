import { expect, type Page, test } from "@playwright/test";

async function inscrire(page: Page, email: string, nom: string) {
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill(nom);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
}

async function ouvrir(page: Page, nom: string) {
  const menu = page.getByRole("combobox", { name: "Onglet" });
  if (await menu.isVisible()) await menu.selectOption({ label: nom });
  else await page.getByRole("tab", { name: nom }).click();
}

test("onglets structure, toiture, solaire et métré", async ({ page }, info) => {
  await inscrire(page, `lot8-${info.project.name}-${Date.now()}@exemple.cd`, "Paul Maçon");
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Villa 3 chambres, toiture 4 pans en tuiles, terrain 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  await expect(page.getByRole("navigation", { name: "Onglets du projet" })).toBeVisible();

  await ouvrir(page, "Structure");
  await expect(page.getByRole("heading", { name: /Semelles filantes/ })).toBeVisible();
  await expect(page.getByTestId("plan").locator("svg .calque-structure")).toBeAttached();
  await expect(page.getByText("À valider par un ingénieur qualifié").first()).toBeVisible();

  await ouvrir(page, "Toiture");
  await expect(page.getByRole("row", { name: /Arêtiers/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /Couverture tuiles/ })).toBeVisible();

  await ouvrir(page, "Solaire");
  await expect(page.locator("dt", { hasText: "Onduleur" })).toBeVisible();

  await ouvrir(page, "Métré & devis");
  await expect(page.getByText("Prix indicatif — à mettre à jour.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Total estimatif/ })).toBeVisible();
  const [csv] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exporter (CSV)" }).click()]);
  expect(csv.suggestedFilename()).toMatch(/-metre\.csv$/);
});

test("l'admin change un prix et le devis le reprend", async ({ page }, info) => {
  test.skip(info.project.name !== "bureau", "un seul compte administrateur pour la base de test");
  await inscrire(page, "admin-e2e@exemple.cd", "Admin");
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Maison 2 chambres, terrain 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  await expect(page.getByRole("navigation", { name: "Onglets du projet" })).toBeVisible();
  const projet = page.url().replace(/\/plan$/, "");
  await ouvrir(page, "Métré & devis");
  const total = page.getByRole("row", { name: /Total estimatif/ });
  const avant = await total.textContent();

  await page.getByRole("link", { name: "Administration" }).click();
  await expect(page.getByRole("heading", { name: "Prix des matériaux" })).toBeVisible();
  await page.getByPlaceholder("Filtrer…").fill("ciment");
  const champ = page.getByLabel(/^Prix de .*[Cc]iment/).first();
  await champ.fill("99,5");
  await page.getByRole("button", { name: "Enregistrer les prix" }).click();
  await expect(page.getByRole("status").filter({ hasText: "1 prix enregistré" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Utilisateurs" })).toBeVisible();

  await page.goto(`${projet}/metre`);
  await page.getByRole("button", { name: "Appliquer les prix actuels" }).click();
  await expect(page.getByText("version 2")).toBeVisible();
  await expect(total).not.toHaveText(avant ?? "");
  await expect(page.getByRole("cell", { name: "99,50 $" }).first()).toBeVisible();
});
