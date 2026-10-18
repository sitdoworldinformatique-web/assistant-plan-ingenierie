import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

test("exports DXF, PDF et XLSX téléchargeables", async ({ page }, info) => {
  await page.goto("/#/connexion");
  await page.getByRole("tab", { name: "Créer un compte" }).click();
  await page.getByLabel("Nom complet").fill("Awa Export");
  await page.getByLabel("Email").fill(`exports-${info.project.name}-${Date.now()}@exemple.cd`);
  await page.getByLabel("Mot de passe").fill("motdepasse123");
  await page.getByRole("button", { name: "Créer le compte" }).click();
  await page.getByRole("link", { name: "+ Nouveau projet" }).click();
  await page.getByLabel("Description de la maison").fill("Maison 3 chambres, terrain 18 m sur 20 m");
  await page.getByRole("button", { name: "Générer" }).click();
  await expect(page.getByRole("navigation", { name: "Onglets du projet" })).toBeVisible();

  const bouton = async (nom: string) => {
    const [d] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: nom, exact: true }).click()]);
    return readFileSync(await d.path()!);
  };
  const dxf = await bouton("Plan DXF");
  expect(dxf.toString("latin1")).toContain("SECTION");
  expect(dxf.toString("latin1")).toContain("MURS");
  const pdf = await bouton("Dossier PDF");
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
  // XLSX = archive zip
  const menu = page.getByRole("combobox", { name: "Onglet" });
  if (await menu.isVisible()) await menu.selectOption({ label: "Métré & devis" });
  else await page.getByRole("tab", { name: "Métré & devis" }).click();
  const xlsx = await bouton("Exporter (XLSX)");
  expect(xlsx.subarray(0, 2).toString()).toBe("PK");
});
