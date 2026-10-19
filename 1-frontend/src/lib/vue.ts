// Transformations de la visionneuse de plan (zoom molette/pincement, déplacement).

export interface Vue {
  s: number;
  tx: number;
  ty: number;
}

export const VUE_INITIALE: Vue = { s: 1, tx: 0, ty: 0 };
export const ZOOM_MIN = 0.5;
export const ZOOM_MAX = 12;

const borner = (s: number) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, s));

/** Zoom d'un facteur `f` autour du point (px, py) exprimé dans le repère du conteneur. */
export function zoomer(v: Vue, f: number, px: number, py: number): Vue {
  const s = borner(v.s * f);
  const k = s / v.s;
  return { s, tx: px - (px - v.tx) * k, ty: py - (py - v.ty) * k };
}

export function deplacer(v: Vue, dx: number, dy: number): Vue {
  return { ...v, tx: v.tx + dx, ty: v.ty + dy };
}
