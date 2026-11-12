import { lazy, Suspense, useEffect, useState } from "react";
import { api, ErreurApi } from "../api/client";
import type { Modele3D, Projet } from "../types";
import BarreCommandes from "./BarreCommandes";
import { Chargement, MessageErreur } from "./Etat";
import PlanViewer from "./PlanViewer";
import RenduAuto from "./RenduAuto";

const Maquette3D = lazy(() => import("./Maquette3D"));

interface Props {
  projet: Projet;
  enCours: boolean;
  peutModifier: boolean;
  onCommande: (texte: string) => Promise<{ comprise: boolean; message: string } | null>;
}

/** Atelier : à gauche le plan de fondation, à droite l'élévation puis la maquette 3D, avec la conversation en haut. */
export default function OngletAtelier({ projet, enCours, peutModifier, onCommande }: Props) {
  const [fondations, setFondations] = useState<string | null>(null);
  const [elevation, setElevation] = useState<string | null>(null);
  const [vue, setVue] = useState<"facade" | "pignon">("facade");
  const [modele, setModele] = useState<Modele3D | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);
  const [capteur, setCapteur] = useState<(() => string) | null>(null);

  useEffect(() => {
    let annule = false;
    setErreur(null);
    const echec = (e: unknown) => !annule && setErreur(e instanceof ErreurApi ? e.message : "Dessin indisponible.");
    api.planSvg(projet.id, ["murs", "cotes", "structure", "annotations"]).then((s) => !annule && setFondations(s)).catch(echec);
    api.modele3d(projet.id).then((m) => !annule && setModele(m)).catch(echec);
    return () => {
      annule = true;
    };
  }, [projet.id, projet.empreinte, projet.version, essai]);

  useEffect(() => {
    let annule = false;
    api.elevation(projet.id, vue).then((s) => !annule && setElevation(s)).catch(() => !annule && setElevation(""));
    return () => {
      annule = true;
    };
  }, [projet.id, projet.empreinte, projet.version, vue]);

  const bloquants = projet.resultats.controles.filter((c) => c.niveau === "bloquant");
  return (
    <div className="atelier">
      <BarreCommandes journal={projet.journal_ia} texteInitial={projet.texte_initial} enCours={enCours} peutModifier={peutModifier} onCommande={onCommande} />
      {erreur && <MessageErreur message={erreur} onReessayer={() => setEssai((n) => n + 1)} />}
      {bloquants.length > 0 && (
        <p className="alerte-atelier" role="status">
          {bloquants.length} point{bloquants.length > 1 ? "s" : ""} bloquant{bloquants.length > 1 ? "s" : ""} : {bloquants[0].titre}. Le détail est dans l'onglet Validation.
        </p>
      )}
      <div className="atelier-grille">
        <section className="carte-atelier" aria-labelledby="titre-fondation">
          <h2 id="titre-fondation">Plan de fondation</h2>
          <p className="texte-2 petit">Semelles filantes en pointillé, poteaux en plein, murs et cotes.</p>
          <div className="atelier-fondation">
            <PlanViewer svg={fondations} selection={null} onSelection={() => undefined} />
          </div>
        </section>
        <div className="atelier-droite">
          <section className="carte-atelier" aria-labelledby="titre-elevation">
            <div className="entete-section">
              <h2 id="titre-elevation">Élévation</h2>
              <div className="segment" role="group" aria-label="Façade">
                <button className={`bouton${vue === "facade" ? " actif" : ""}`} aria-pressed={vue === "facade"} onClick={() => setVue("facade")}>
                  Principale
                </button>
                <button className={`bouton${vue === "pignon" ? " actif" : ""}`} aria-pressed={vue === "pignon"} onClick={() => setVue("pignon")}>
                  Latérale
                </button>
              </div>
            </div>
            <div className="atelier-elevation">
              <PlanViewer svg={elevation} selection={null} onSelection={() => undefined} />
            </div>
          </section>
          <section className="carte-atelier" aria-labelledby="titre-3d">
            <h2 id="titre-3d">Maquette 3D</h2>
            {modele ? (
              <Suspense fallback={<Chargement texte="Chargement de la 3D…" />}>
                <Maquette3D modele={modele} onCapteur={(f) => setCapteur(() => f)} />
              </Suspense>
            ) : (
              <Chargement texte="Calcul des volumes…" />
            )}
            {modele && (
              <details className="hypotheses-3d">
                <summary>Hypothèses de la maquette</summary>
                <ul>
                  {modele.hypotheses.map((h) => (
                    <li key={h}>{h}</li>
                  ))}
                </ul>
                <p className="petit">{modele.mention}</p>
              </details>
            )}
          </section>
          <RenduAuto projet={projet} capteur={capteur} peutModifier={peutModifier} />
        </div>
      </div>
    </div>
  );
}
