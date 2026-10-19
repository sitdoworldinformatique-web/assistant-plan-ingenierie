import { expect, test } from "@playwright/test";

test("atelier : décrire, préciser étape par étape, 3D, annuler", async ({ page }, info) => {
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Awa Atelier");
  await page.getByLabel("Email").fill(`atelier-${info.project.name}-${Date.now()}@exemple.cd`);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Villa 3 chambres avec séjour, cuisine, 2 douches, terrain 25 m sur 30 m");
  await page.getByRole("button", { name: "Générer" }).click();

  await expect(page).toHaveURL(/#\/projets\/\d+\/atelier$/);
  await expect(page.getByRole("heading", { name: "Plan de fondation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Élévation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Maquette 3D" })).toBeVisible();
  await expect(page.getByTestId("maquette-3d").locator("canvas")).toBeVisible();
  await expect(page.locator(".atelier-elevation svg").first()).toBeVisible();

  const commande = page.locator("#commande");
  await commande.fill("ajoute une chambre");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await expect(page.getByText("Chambres : 3 → 4").first()).toBeVisible();

  await page.getByRole("button", { name: "Toiture 4 pans en tuiles" }).click();
  await expect(page.getByText("Toiture : 2 pans → 4 pans").first()).toBeVisible();

  await commande.fill("fais quelque chose de joli");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await expect(page.getByText(/non comprise/i).first()).toBeVisible();

  await page.getByRole("button", { name: "Annule la dernière étape" }).click();
  await expect(page.getByText(/annul/i).first()).toBeVisible();
});
