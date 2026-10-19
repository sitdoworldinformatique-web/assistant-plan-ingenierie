import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

test("texte → plan affiché → export SVG", async ({ page }, info) => {
  const email = `constructeur-${info.project.name}-${Date.now()}@exemple.cd`;
  await page.goto("/");

  // Inscription
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Jean Bâtisseur");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await expect(page.getByRole("heading", { name: "Mes projets" })).toBeVisible();

  // Description puis génération (sans clé IA : analyseur par règles)
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page
    .getByLabel("Description de la maison")
    .fill("Villa de 3 chambres avec salon, cuisine fermée, une salle de bain, WC séparé et véranda, sur un terrain de 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();

  await expect(page).toHaveURL(/#\/projets\/\d+\/atelier$/);
  const menuPlan = page.getByRole("combobox", { name: "Onglet" });
  if (await menuPlan.isVisible()) await menuPlan.selectOption({ label: "Plan" });
  else await page.getByRole("tab", { name: "Plan", exact: true }).click();
  await expect(page.getByText("analyseur par règles (IA non configurée)")).toBeVisible();
  const plan = page.getByTestId("plan");
  await expect(plan.locator("svg rect.piece").first()).toBeVisible();
  expect(await plan.locator("svg rect.piece").count()).toBeGreaterThanOrEqual(8);
  await expect(plan.locator("svg").getByText("Séjour", { exact: false }).first()).toBeAttached();

  // Clic sur une pièce → panneau latéral
  await plan.locator('svg rect.piece[data-piece="SEJ"]').click({ force: true });
  await expect(page.getByRole("heading", { name: "Séjour" })).toBeVisible();
  await expect(page.getByText("Surface nette")).toBeVisible();

  // Export SVG
  const [telechargement] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exporter le plan (SVG)" }).click()]);
  expect(telechargement.suggestedFilename()).toMatch(/\.svg$/);
  const svg = await readFile((await telechargement.path())!, "utf-8");
  expect(svg.startsWith("<svg") || svg.startsWith("<?xml")).toBeTruthy();
  expect(svg).toContain('class="calque-murs"');
  expect(svg).toContain("Chambre");
  expect(svg).toContain("À valider par un ingénieur");
});

test("onglets programme, électricité et validation", async ({ page }, info) => {
  const email = `ing-${info.project.name}-${Date.now()}@exemple.cd`;
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Marie Constructrice");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Maison 2 chambres, terrain 16 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  await expect(page).toHaveURL(/#\/projets\/\d+\/atelier$/);

  await expect(page.getByRole("navigation", { name: "Onglets du projet" })).toBeVisible();
  const ouvrir = async (nom: string) => {
    const menu = page.getByRole("combobox", { name: "Onglet" });
    if (await menu.isVisible()) await menu.selectOption({ label: nom });
    else await page.getByRole("tab", { name: nom }).click();
  };

  // Électricité : tableau groupé par différentiel et schéma unifilaire
  await ouvrir("Électricité");
  await expect(page.getByRole("heading", { name: "Circuits par interrupteur différentiel" })).toBeVisible();
  await expect(page.getByText(/^ID1 · 30 mA/)).toBeVisible();
  await expect(page.locator(".unifilaire svg")).toBeAttached();

  // Programme : recalcul avec une chambre de plus
  await ouvrir("Programme");
  await page.getByLabel("Chambres", { exact: true }).fill("3");
  await page.getByRole("button", { name: "Recalculer" }).click();
  await expect(page.getByText("version 2")).toBeVisible();

  // Validation : rapport, explication sans IA, signature réservée à l'ingénieur
  await ouvrir("Validation");
  await expect(page.getByRole("heading", { name: "Rapport de conformité" })).toBeVisible();
  await page.getByRole("button", { name: "Expliquer" }).first().click();
  await expect(page.getByText("Texte du moteur de calcul").first()).toBeVisible();
  await expect(page.getByText("Seul un ingénieur peut signer.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Bon pour exécution" })).toBeDisabled();
});
