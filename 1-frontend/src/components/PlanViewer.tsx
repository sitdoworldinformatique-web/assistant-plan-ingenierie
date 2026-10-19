import { useCallback, useEffect, useRef, useState } from "react";
import { deplacer, type Vue, VUE_INITIALE, zoomer } from "../lib/vue";

interface Props {
  svg: string | null;
  selection: string | null;
  onSelection: (pieceId: string | null) => void;
}

/** Affiche le SVG technique : zoom molette ou pincement, déplacement, bouton « ajuster », clic sur une pièce. */
export default function PlanViewer({ svg, selection, onSelection }: Props) {
  const cadre = useRef<HTMLDivElement>(null);
  const contenu = useRef<HTMLDivElement>(null);
  const [vue, setVue] = useState<Vue>(VUE_INITIALE);
  const pointeurs = useRef(new Map<number, { x: number; y: number }>());
  const geste = useRef({ bouge: 0, distance: 0 });

  // Insertion du SVG, mis à l'échelle du cadre (les dimensions en mm servent à l'impression)
  useEffect(() => {
    const el = contenu.current;
    if (!el) return;
    el.innerHTML = svg ?? "";
    const s = el.querySelector("svg");
    if (s) {
      s.removeAttribute("width");
      s.removeAttribute("height");
      s.setAttribute("preserveAspectRatio", "xMidYMid meet");
      s.setAttribute("role", "img");
    }
  }, [svg]);

  useEffect(() => {
    const el = contenu.current;
    if (!el) return;
    el.querySelectorAll(".selectionnee").forEach((n) => n.classList.remove("selectionnee"));
    if (selection) el.querySelectorAll(`rect.piece[data-piece="${CSS.escape(selection)}"]`).forEach((n) => n.classList.add("selectionnee"));
  }, [selection, svg]);

  // Molette : écouteur non passif pour empêcher le défilement de la page
  useEffect(() => {
    const el = cadre.current;
    if (!el) return;
    const roue = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      setVue((v) => zoomer(v, Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top));
    };
    el.addEventListener("wheel", roue, { passive: false });
    return () => el.removeEventListener("wheel", roue);
  }, []);

  const local = (e: React.PointerEvent) => {
    const r = cadre.current!.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };

  const bas = (e: React.PointerEvent) => {
    cadre.current?.setPointerCapture(e.pointerId);
    pointeurs.current.set(e.pointerId, local(e));
    geste.current.bouge = 0;
    if (pointeurs.current.size === 2) {
      const [a, b] = [...pointeurs.current.values()];
      geste.current.distance = Math.hypot(a.x - b.x, a.y - b.y);
    }
  };

  const mouvement = (e: React.PointerEvent) => {
    const avant = pointeurs.current.get(e.pointerId);
    if (!avant) return;
    const p = local(e);
    pointeurs.current.set(e.pointerId, p);
    if (pointeurs.current.size === 1) {
      geste.current.bouge += Math.abs(p.x - avant.x) + Math.abs(p.y - avant.y);
      setVue((v) => deplacer(v, p.x - avant.x, p.y - avant.y));
    } else if (pointeurs.current.size === 2) {
      const [a, b] = [...pointeurs.current.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      if (geste.current.distance > 0) setVue((v) => zoomer(v, d / geste.current.distance, (a.x + b.x) / 2, (a.y + b.y) / 2));
      geste.current.distance = d;
      geste.current.bouge = 99;
    }
  };

  const haut = (e: React.PointerEvent) => {
    const etaitSeul = pointeurs.current.size === 1;
    pointeurs.current.delete(e.pointerId);
    if (etaitSeul && geste.current.bouge < 5) {
      // Clic (pas un déplacement) : sélection de la pièce sous le pointeur
      const cible = document.elementsFromPoint(e.clientX, e.clientY).find((n) => n instanceof SVGElement && n.dataset.piece);
      onSelection((cible as SVGElement | undefined)?.dataset.piece ?? null);
    }
  };

  const ajuster = useCallback(() => setVue(VUE_INITIALE), []);
  const zoomBouton = (f: number) => {
    const r = cadre.current!.getBoundingClientRect();
    setVue((v) => zoomer(v, f, r.width / 2, r.height / 2));
  };
  const pleinEcran = () => {
    const el = cadre.current?.parentElement;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  };

  return (
    <div className="plan-viewer">
      <div className="plan-outils" role="toolbar" aria-label="Outils du plan">
        <button className="bouton" onClick={() => zoomBouton(1.25)} aria-label="Zoomer">
          +
        </button>
        <button className="bouton" onClick={() => zoomBouton(0.8)} aria-label="Dézoomer">
          −
        </button>
        <button className="bouton" onClick={ajuster}>
          Ajuster
        </button>
        <button className="bouton" onClick={pleinEcran}>
          Plein écran
        </button>
      </div>
      <div
        ref={cadre}
        className="plan-cadre"
        onPointerDown={bas}
        onPointerMove={mouvement}
        onPointerUp={haut}
        onPointerCancel={(e) => pointeurs.current.delete(e.pointerId)}
        data-testid="plan"
      >
        <div
          ref={contenu}
          className="plan-contenu"
          style={{ transform: `translate(${vue.tx}px, ${vue.ty}px) scale(${vue.s})` }}
        />
      </div>
    </div>
  );
}
