import { describe, expect, it } from "vitest";
import { deplacer, VUE_INITIALE, zoomer, ZOOM_MAX } from "./vue";

describe("visionneuse", () => {
  it("le point sous le curseur reste fixe pendant le zoom", () => {
    const v = zoomer(VUE_INITIALE, 2, 100, 50);
    // point écran (100, 50) → point plan ((100 - tx) / s)
    expect((100 - v.tx) / v.s).toBeCloseTo(100);
    expect((50 - v.ty) / v.s).toBeCloseTo(50);
  });
  it("zoom borné et déplacement", () => {
    expect(zoomer(VUE_INITIALE, 1000, 0, 0).s).toBe(ZOOM_MAX);
    expect(deplacer(VUE_INITIALE, 5, -3)).toEqual({ s: 1, tx: 5, ty: -3 });
  });
});
