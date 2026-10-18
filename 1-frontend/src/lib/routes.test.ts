import { describe, expect, it } from "vitest";
import { lienRoute, lireRoute } from "./routes";

describe("routes", () => {
  it("lit les fragments", () => {
    expect(lireRoute("")).toEqual({ page: "projets" });
    expect(lireRoute("#/connexion")).toEqual({ page: "connexion" });
    expect(lireRoute("#/projets/nouveau")).toEqual({ page: "nouveau" });
    expect(lireRoute("#/projets/12/electricite")).toEqual({ page: "projet", id: 12, onglet: "electricite" });
    expect(lireRoute("#/projets/abc")).toEqual({ page: "projets" });
  });
  it("aller-retour", () => {
    expect(lireRoute(lienRoute({ page: "projet", id: 3, onglet: "plan" }))).toEqual({ page: "projet", id: 3, onglet: "plan" });
  });
});
