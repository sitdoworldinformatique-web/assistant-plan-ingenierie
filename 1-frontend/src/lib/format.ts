// Formats français : virgule décimale, espace fine insécable pour les milliers.

const ESPACE = " ";

export function nombre(valeur: number | null | undefined, decimales = 2): string {
  if (valeur === null || valeur === undefined || Number.isNaN(valeur)) return "—";
  const fixe = Math.abs(valeur).toFixed(decimales);
  const [entier, frac] = fixe.split(".");
  const groupes = entier.replace(/\B(?=(\d{3})+(?!\d))/g, ESPACE);
  const signe = valeur < 0 && Number(fixe) !== 0 ? "-" : "";
  return signe + groupes + (frac ? "," + frac : "");
}

export const metres = (v: number, d = 2) => `${nombre(v, d)} m`;
export const surface = (v: number, d = 2) => `${nombre(v, d)} m²`;
export const pourcent = (v: number, d = 2) => `${nombre(v, d)} %`;

export function monnaie(v: number, devise = "USD"): string {
  return `${nombre(v, 2)} ${devise === "USD" ? "$" : devise}`;
}

export function date(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function dateHeure(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Lit un nombre saisi en français (« 12,5 ») ou en notation point. */
export function lireNombre(texte: string): number | null {
  const t = texte.replace(/[\s  ]/g, "").replace(",", ".");
  if (t === "" || !/^-?\d*\.?\d+$/.test(t)) return null;
  return Number(t);
}

export const LIBELLES_STATUT: Record<string, string> = {
  conforme: "Conforme",
  conforme_avec_reserves: "Conforme avec réserves",
  bloque: "Bloqué",
};

export const LIBELLES_NIVEAU: Record<string, string> = {
  ok: "Conforme",
  avertissement: "Avertissement",
  bloquant: "Bloquant",
};
