import { useEffect, useRef, useState } from "react";
import { api, ErreurApi } from "../api/client";
import { metres, nombre, surface } from "../lib/format";
import { nomFichier, telecharger } from "../lib/telecharger";
import type { Projet } from "../types";
import CalquesPlan, { CALQUES_DEFAUT } from "./CalquesPlan";
import { MessageErreur } from "./Etat";
import PlanViewer from "./PlanViewer";

const TYPES: Record<string, string> = {
  chambre: "Chambre",
  sejour: "Séjour",
  cuisine: "Cuisine",
  sdb: "Salle de bain",
  wc: "WC",
  couloir: "Dégagement",
  placard: "Placard",
  bureau: "Bureau",
  garage: "Garage",
  veranda: "Véranda",
};

const LIBELLES_POINTS: Record<string, [string, string]> = {
  lumiere: ["point lumineux", "points lumineux"],
  prise: ["prise", "prises"],
  interrupteur: ["interrupteur", "interrupteurs"],
  prise_specialisee: ["prise spécialisée", "prises spécialisées"],
  tableau: ["tableau", "tableaux"],
};

export default function OngletPlan({ projet }: { projet: Projet }) {
  const [calques, setCalques] = useState<string[]>(CALQUES_DEFAUT);
  const [svg, setSvg] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const cache = useRef(new Map<string, string>());
  const [essai, setEssai] = useState(0);

  useEffect(() => cache.current.clear(), [projet.empreinte, projet.version]);

  useEffect(() => {
    const cle = calques.join(",");
    const connu = cache.current.get(cle);
    if (connu) {
      setSvg(connu);
      return;
    }
    let annule = false;
    setErreur(null);
    api
      .planSvg(projet.id, calques)
      .then((s) => {
        cache.current.set(cle, s);
        if (!annule) setSvg(s);
      })
      .catch((e) => !annule && setErreur(e instanceof ErreurApi ? e.message : "Plan indisponible."));
    return () => {
      annule = true;
    };
  }, [projet.id, projet.empreinte, projet.version, calques, essai]);

  const piece = projet.resultats.implantation.pieces.find((p) => p.id === selection);
  const points = piece
    ? projet.resultats.electricite.points?.filter((p) => p.piece_id === piece.id) ?? []
    : [];
  const compte = points.reduce<Record<string, number>>((acc, p) => ({ ...acc, [p.type]: (acc[p.type] ?? 0) + 1 }), {});

  return (
    <div className="onglet-plan">
      <aside className="plan-cote-gauche">
        <CalquesPlan actifs={calques} onChange={setCalques} />
        <button className="bouton" onClick={() => svg && telecharger(svg, nomFichier(projet.nom, "svg"), "image/svg+xml")} disabled={!svg}>
          Exporter ces calques (SVG)
        </button>
        {piece ? (
          <div className="panneau-piece" aria-live="polite">
            <h3>{piece.nom}</h3>
            <dl>
              <div>
                <dt>Type</dt>
                <dd>{TYPES[piece.type] ?? piece.type}</dd>
              </div>
              <div>
                <dt>Dimensions nettes</dt>
                <dd>
                  {metres(piece.net.l)} × {metres(piece.net.p)}
                </dd>
              </div>
              <div>
                <dt>Surface nette</dt>
                <dd>{surface(piece.surface_nette)}</dd>
              </div>
              <div>
                <dt>Habitable</dt>
                <dd>{piece.habitable ? "oui" : "non"}</dd>
              </div>
              {Object.keys(compte).length > 0 && (
                <div>
                  <dt>Électricité</dt>
                  <dd>
                    {Object.entries(compte)
                      .map(([t, n]) => `${nombre(n, 0)} ${LIBELLES_POINTS[t]?.[n > 1 ? 1 : 0] ?? t}`)
                      .join(", ")}
                  </dd>
                </div>
              )}
            </dl>
            <button className="lien" onClick={() => setSelection(null)}>
              Fermer
            </button>
          </div>
        ) : (
          <p className="texte-2 petit">Cliquez sur une pièce pour voir ses données.</p>
        )}
      </aside>
      <div className="plan-principal">
        {erreur ? <MessageErreur message={erreur} onReessayer={() => setEssai((n) => n + 1)} /> : <PlanViewer svg={svg} selection={selection} onSelection={setSelection} />}
      </div>
    </div>
  );
}
