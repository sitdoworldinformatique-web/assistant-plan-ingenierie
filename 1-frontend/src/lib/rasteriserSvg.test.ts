import { describe, expect, it } from "vitest";
import { dimensions, preparer } from "./rasteriserSvg";

const SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="174.8mm" height="120mm" viewBox="0 0 1748 1200"><rect/></svg>';

describe("rasterisation du plan", () => {
  it("garde les proportions du viewBox", () => {
    expect(dimensions(SVG)).toEqual({ largeur: 2048, hauteur: 1406 });
  });
  it("remplace les dimensions en mm par des pixels", () => {
    const s = preparer(SVG);
    expect(s).toContain('width="2048" height="1406"');
    expect(s).not.toContain("mm");
    expect(s.match(/xmlns=/g)).toHaveLength(1);
  });
  it("refuse un SVG sans viewBox", () => {
    expect(() => dimensions("<svg></svg>")).toThrow();
  });
});
