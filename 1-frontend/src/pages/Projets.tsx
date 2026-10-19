import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErreurApi } from "../api/client";
import { Chargement, MessageErreur, Pastille } from "../components/Etat";
import { date } from "../lib/format";
import type { ResumeProjet, Utilisateur } from "../types";

function Miniature({ id }: { id: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Chargée seulement quand la carte devient visible
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) {
        obs.disconnect();
        api.planSvg(id, ["murs"]).then(setSvg).catch(() => setSvg(""));
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, [id]);
  return (
    <div ref={ref} className="miniature" aria-hidden="true">
      {svg ? <div className="miniature-svg" dangerouslySetInnerHTML={{ __html: svg }} /> : null}
    </div>
  );
}

export default function Projets({ utilisateur }: { utilisateur: Utilisateur }) {
  const [projets, setProjets] = useState<ResumeProjet[] | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  const charger = useCallback(() => {
    setErreur(null);
    api
      .projets()
      .then(setProjets)
      .catch((e) => setErreur(e instanceof ErreurApi ? e.message : "Erreur inattendue."));
  }, []);
  useEffect(charger, [charger]);

  return (
    <main className="page">
      <div className="entete-page">
        <h1>{utilisateur.role === "constructeur" ? "Mes projets" : "Projets"}</h1>
        <a className="bouton bouton-principal" href="#/projets/nouveau">
          + Nouveau projet
        </a>
      </div>
      {erreur && <MessageErreur message={erreur} onReessayer={charger} />}
      {!projets && !erreur && <Chargement />}
      {projets && projets.length === 0 && (
        <div className="vide">
          <p>Aucun projet pour l'instant.</p>
          <p className="texte-2">Créez-en un en décrivant la maison en quelques phrases.</p>
        </div>
      )}
      {projets && projets.length > 0 && (
        <ul className="grille-projets">
          {projets.map((p) => (
            <li key={p.id}>
              <a className="carte carte-projet" href={`#/projets/${p.id}`}>
                <Miniature id={p.id} />
                <div className="carte-projet-corps">
                  <h2>{p.nom}</h2>
                  <p className="texte-2">
                    Modifié le {date(p.modifie_le)} · version {p.version}
                  </p>
                  <Pastille statut={p.statut} />
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
