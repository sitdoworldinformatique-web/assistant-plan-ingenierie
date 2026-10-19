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

test("atelier : rendu réaliste automatique depuis la maquette 3D", async ({ page }, info) => {
  const PNG_1PX = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64");
  const envois: { style: string; image_base64: string }[] = [];
  const rendus: object[] = [];
  await page.route(/\/api\/projets\/\d+\/rendus$/, async (route) => {
    if (route.request().method() === "POST") {
      const corps = route.request().postDataJSON();
      envois.push(corps);
      const r = { id: envois.length, style: corps.style, libelle: "Rendu réaliste", date: new Date().toISOString(), modele: "simule",
        mention: "Image de présentation — non contractuelle. Cotes et quantités : voir plan technique", url: "/api/projets/0/rendus/1.jpg" };
      rendus.length = 0;
      rendus.push(r);
      return route.fulfill({ status: 201, json: r });
    }
    const vraie = await (await route.fetch()).json();
    return route.fulfill({ json: { ...vraie, ia_image_configuree: true, rendus, quota: { max: 10, utilises: envois.length } } });
  });
  await page.route("**/api/projets/0/rendus/1.jpg", (route) => route.fulfill({ body: PNG_1PX, contentType: "image/png" }));

  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Awa Rendu");
  await page.getByLabel("Email").fill(`rendu-auto-${info.project.name}-${Date.now()}@exemple.cd`);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Villa 3 chambres avec séjour, cuisine, 2 douches, terrain 25 m sur 30 m");
  await page.getByRole("button", { name: "Générer" }).click();

  // Le rendu part tout seul, avec une capture de la 3D
  await expect(page.getByRole("img", { name: /Rendu réaliste/ })).toBeVisible({ timeout: 20_000 });
  expect(envois).toHaveLength(1);
  expect(envois[0].style).toBe("realiste");
  const png = Buffer.from(envois[0].image_base64.replace(/^data:[^,]*,/, ""), "base64");
  expect(png.subarray(1, 4).toString()).toBe("PNG");
  expect(png.length).toBeGreaterThan(5_000); // la maison est réellement dessinée

  // Une étape de plus : un nouveau rendu est demandé
  await page.locator("#commande").fill("ajoute une chambre");
  await page.getByRole("button", { name: "Envoyer" }).click();
  await expect.poll(() => envois.length, { timeout: 20_000 }).toBe(2);
});
