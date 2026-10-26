import { describe, expect, it } from "vitest";
import { lireNombre, monnaie, nombre, surface } from "./format";

describe("formats français", () => {
  it("virgule décimale et milliers", () => {
    expect(nombre(12.4)).toBe("12,40");
    expect(surface(12.4)).toBe("12,40 m²");
    expect(nombre(1234567.891, 1)).toBe("1 234 567,9");
    expect(nombre(-0.001)).toBe("0,00");
    expect(nombre(-3.5, 1)).toBe("-3,5");
    expect(nombre(null)).toBe("—");
    expect(monnaie(15000)).toBe("15 000,00 $");
  });
  it("lecture des saisies", () => {
    expect(lireNombre("12,5")).toBe(12.5);
    expect(lireNombre(" 1 200,75 ")).toBe(1200.75);
    expect(lireNombre("3.2")).toBe(3.2);
    expect(lireNombre("abc")).toBeNull();
    expect(lireNombre("")).toBeNull();
  });
});
