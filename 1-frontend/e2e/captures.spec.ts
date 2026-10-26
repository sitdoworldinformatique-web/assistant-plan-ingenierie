import { expect, test } from "@playwright/test";

// Captures pour la revue visuelle : CAPTURES=1 npx playwright test captures --project=bureau
test.skip(!process.env.CAPTURES, "captures à la demande");

test("captures des écrans du lot 7", async ({ page }, info) => {
  const dossier = "../docs/captures";
  const nom = info.project.name;
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Jean Bâtisseur");
  await page.getByLabel("Email").fill(`capture-${nom}-${Date.now()}@exemple.cd`);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page
    .getByLabel("Description de la maison")
    .fill("Villa de 3 chambres avec salon, cuisine fermée, une salle de bain, WC séparé et véranda, sur un terrain de 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  const menuPlan = page.getByRole("combobox", { name: "Onglet" });
  if (await menuPlan.isVisible()) await menuPlan.selectOption({ label: "Plan" });
  else await page.getByRole("tab", { name: "Plan", exact: true }).click();
  await expect(page.getByTestId("plan").locator("svg rect.piece").first()).toBeVisible();
  await page.getByTestId("plan").locator('svg rect.piece[data-piece="SEJ"]').click({ force: true });
  await page.screenshot({ path: `${dossier}/lot7-plan-${nom}.png`, fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.screenshot({ path: `${dossier}/lot7-plan-${nom}-sombre.png`, fullPage: true });
  await page.emulateMedia({ colorScheme: "light" });
  const url = page.url().replace(/\/(plan|atelier)$/, "");
  for (const onglet of ["electricite", "validation", "programme", "structure", "toiture", "solaire", "metre"]) {
    await page.goto(`${url}/${onglet}`);
    await page.waitForLoadState("networkidle");
    if (onglet === "validation") await page.getByRole("button", { name: "Expliquer" }).first().click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${dossier}/lot7-${onglet}-${nom}.png`, fullPage: true });
  }
  await page.goto("/#/projets");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${dossier}/lot7-projets-${nom}.png` });
});
