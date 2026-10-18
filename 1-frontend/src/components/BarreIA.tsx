import { type FormEvent, useEffect, useState } from "react";
import type { Correction, EntreeJournal } from "../types";

const ETAPES = [
  { id: "interpreter", libelle: "Interpréter la description" },
  { id: "calculer", libelle: "Calculer plan, électricité, structure, toiture, métré" },
  { id: "controler", libelle: "Contrôler les règles" },
  { id: "corriger", libelle: "Corriger automatiquement les bloquants" },
];

export interface Bilan {
  journal: EntreeJournal[];
  corrections: Correction[];
  remarques: string[];
  bloquants: number;
}

interface Props {
  texteInitial?: string;
  iaConfiguree: boolean | null;
  enCours: boolean;
  bilan: Bilan | null;
  onGenerer: (texte: string) => void;
}

function resumeEtape(id: string, b: Bilan, iaConfiguree: boolean | null): string {
  const interp = b.journal.filter((e) => e.etape === "interpreter");
  const derniere = interp[interp.length - 1];
  switch (id) {
    case "interpreter":
      if (!derniere) return "programme saisi";
      return derniere.modele === "analyseur-par-regles"
        ? iaConfiguree
          ? "analyseur par règles (l'IA n'a pas répondu)"
          : "analyseur par règles (IA non configurée)"
        : `par ${derniere.modele}`;
    case "calculer":
      return "fait";
    case "controler":
      return b.bloquants ? `${b.bloquants} bloquant${b.bloquants > 1 ? "s" : ""}` : "aucun bloquant";
    case "corriger":
      if (b.corrections.length) return `${b.corrections.length} correction${b.corrections.length > 1 ? "s" : ""} appliquée${b.corrections.length > 1 ? "s" : ""}`;
      return iaConfiguree ? "aucune correction" : "sans IA : bloquants affichés";
  }
  return "";
}

export default function BarreIA({ texteInitial = "", iaConfiguree, enCours, bilan, onGenerer }: Props) {
  const [texte, setTexte] = useState(texteInitial);
  useEffect(() => setTexte(texteInitial), [texteInitial]);
  const [secondes, setSecondes] = useState(0);
  useEffect(() => {
    if (!enCours) return;
    setSecondes(0);
    const t = setInterval(() => setSecondes((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [enCours]);

  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    if (texte.trim()) onGenerer(texte.trim());
  };

  return (
    <section className="barre-ia" aria-label="Barre IA">
      <form onSubmit={envoyer}>
        <label htmlFor="description" className="visuellement-cache">
          Description de la maison
        </label>
        <textarea
          id="description"
          value={texte}
          onChange={(e) => setTexte(e.target.value)}
          placeholder="Décrivez la maison… ex. Villa de 3 chambres avec salon, cuisine fermée, véranda, sur un terrain de 15 m sur 20 m"
          rows={3}
          maxLength={5000}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) envoyer(e);
          }}
        />
        <button className="bouton bouton-principal" type="submit" disabled={enCours || !texte.trim()}>
          {enCours ? "Génération…" : "Générer"}
        </button>
      </form>
      {iaConfiguree === false && !enCours && !bilan && (
        <p className="aide">IA non configurée sur ce serveur : la description est lue par l'analyseur par règles.</p>
      )}
      {(enCours || bilan) && (
        <ol className="pipeline" aria-live="polite">
          {ETAPES.map((e) => (
            <li key={e.id} className={enCours ? "en-cours" : "fait"}>
              <span className="pipeline-icone" aria-hidden="true">
                {enCours ? "✱" : "✓"}
              </span>
              <span>{e.libelle}</span>
              {!enCours && bilan && <span className="texte-2"> · {resumeEtape(e.id, bilan, iaConfiguree)}</span>}
            </li>
          ))}
          {enCours && <li className="texte-2">En cours depuis {secondes} s…</li>}
        </ol>
      )}
      {!enCours && bilan && bilan.corrections.length > 0 && (
        <div className="corrections">
          <strong>Corrections proposées par l'IA et recalculées :</strong>
          <ul>
            {bilan.corrections.map((c) => (
              <li key={c.iteration}>
                {c.explication || "Correction"} <span className="texte-2">({c.champs_modifies.join(", ")})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {!enCours && bilan && bilan.remarques.length > 0 && (
        <div className="remarques">
          <strong>À vérifier :</strong>
          <ul>
            {bilan.remarques.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
