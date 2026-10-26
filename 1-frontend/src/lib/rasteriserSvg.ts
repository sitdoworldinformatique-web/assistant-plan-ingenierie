// Rasterisation du plan technique (SVG) en PNG dans le navigateur, sans dépendance serveur (CdC § 8).

export const LARGEUR_RENDU_PX = 2048;

/** Dimensions en pixels à partir du viewBox, pour une largeur donnée. */
export function dimensions(svg: string, largeur = LARGEUR_RENDU_PX): { largeur: number; hauteur: number } {
  const m = svg.match(/viewBox="\s*([-\d.]+)[\s,]+([-\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)\s*"/);
  if (!m) throw new Error("SVG sans viewBox");
  const [l, h] = [Number(m[3]), Number(m[4])];
  return { largeur, hauteur: Math.round((largeur * h) / l) };
}

/** Fixe la taille en pixels (le SVG technique est dimensionné en mm pour l'impression). */
export function preparer(svg: string, largeur = LARGEUR_RENDU_PX): string {
  const d = dimensions(svg, largeur);
  return svg.replace(/<svg\b([^>]*)>/, (_tout, attrs: string) => {
    const nettoye = attrs.replace(/\s(width|height)="[^"]*"/g, "");
    const ns = nettoye.includes("xmlns=") ? "" : ' xmlns="http://www.w3.org/2000/svg"';
    return `<svg${nettoye}${ns} width="${d.largeur}" height="${d.hauteur}">`;
  });
}

/** SVG → PNG base64 (sans le préfixe data:), sur fond blanc. */
export async function rasteriser(svg: string, largeur = LARGEUR_RENDU_PX): Promise<string> {
  const pret = preparer(svg, largeur);
  const { hauteur } = dimensions(svg, largeur);
  const url = URL.createObjectURL(new Blob([pret], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.decoding = "async";
    await new Promise<void>((ok, ko) => {
      img.onload = () => ok();
      img.onerror = () => ko(new Error("Le plan n'a pas pu être converti en image."));
      img.src = url;
    });
    const canvas = document.createElement("canvas");
    canvas.width = largeur;
    canvas.height = hauteur;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas indisponible.");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, largeur, hauteur);
    ctx.drawImage(img, 0, 0, largeur, hauteur);
    return canvas.toDataURL("image/png").split(",", 2)[1];
  } finally {
    URL.revokeObjectURL(url);
  }
}
