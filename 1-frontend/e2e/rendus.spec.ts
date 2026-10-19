import { writeFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";

// Le service d'images est simulé au niveau du navigateur : on vérifie la rasterisation du plan,
// la requête envoyée à l'API et l'affichage de la galerie avec la mention « non contractuelle ».
const PNG_1PX = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");

test("rendus IA : sans clé, puis avec un service simulé", async ({ page }, info) => {
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Awa Architecte");
  await page.getByLabel("Email").fill(`rendus-${info.project.name}-${Date.now()}@exemple.cd`);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Villa 3 chambres avec véranda, terrain 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  await expect(page.getByRole("navigation", { name: "Onglets du projet" })).toBeVisible();
  const projet = page.url().replace(/\/(plan|atelier)$/, "");

  // 1. Sans clé : message clair, pas de bouton
  await page.goto(`${projet}/rendus`);
  await expect(page.getByText("Les rendus IA sont désactivés")).toBeVisible();
  await expect(page.getByRole("button", { name: "Générer l'image" })).toHaveCount(0);

  // 2. Service simulé
  let envoi: { style: string; image_base64: string } | null = null;
  const rendus: object[] = [];
  await page.route(/\/api\/projets\/\d+\/rendus$/, async (route) => {
    if (route.request().method() === "POST") {
      envoi = route.request().postDataJSON();
      const r = { id: 1, style: envoi!.style, libelle: "Façade principale", date: new Date().toISOString(), modele: "simule",
        mention: "Image de présentation — non contractuelle. Cotes et quantités : voir plan technique", url: "/api/projets/0/rendus/1.jpg" };
      rendus.push(r);
      return route.fulfill({ status: 201, json: r });
    }
    const vraie = await (await route.fetch()).json();
    return route.fulfill({ json: { ...vraie, ia_image_configuree: true, rendus, quota: { max: 10, utilises: rendus.length } } });
  });
  await page.route("**/api/projets/0/rendus/1.jpg", (route) => route.fulfill({ body: PNG_1PX, contentType: "image/png" }));
  await page.reload();

  await expect(page.getByText("10 rendus restants aujourd'hui")).toBeVisible();
  await page.getByRole("radio", { name: /Façade principale/ }).check({ force: true });
  await page.getByRole("button", { name: "Générer l'image" }).click();
  await expect(page.getByRole("img", { name: /non contractuelle/ })).toBeVisible();
  await expect(page.locator(".mention-rendu")).toHaveText(/non contractuelle/);

  expect(envoi!.style).toBe("facade");
  const png = Buffer.from(envoi!.image_base64, "base64");
  expect(png.subarray(1, 4).toString()).toBe("PNG");
  expect(png.readUInt32BE(16)).toBe(2048); // largeur du PNG envoyé
  expect(png.length).toBeGreaterThan(10_000); // le plan est réellement dessiné
  if (process.env.CAPTURES && info.project.name === "bureau") {
    await writeFile("../docs/captures/lot9-plan-rasterise.png", png);
    await page.screenshot({ path: "../docs/captures/lot9-rendus-bureau.png", fullPage: true });
  }
});
