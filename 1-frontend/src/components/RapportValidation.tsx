import { useMemo, useState } from "react";
import { api, ErreurApi } from "../api/client";
import { LIBELLES_MODULES, MODULES, type Module, type Niveau, type Projet } from "../types";
import { Pastille } from "./Etat";

const ORDRE: Record<Niveau, number> = { bloquant: 0, avertissement: 1, ok: 2 };

export default function RapportValidation({ projet }: { projet: Projet }) {
  const [niveau, setNiveau] = useState<Niveau | "tous">("tous");
  const [module, setModule] = useState<Module | "tous">("tous");
  const [explications, setExplications] = useState<Record<string, { texte: string; source: string } | "chargement" | { erreur: string }>>({});

  const controles = useMemo(
    () =>
      projet.resultats.controles
        .filter((c) => (niveau === "tous" || c.niveau === niveau) && (module === "tous" || c.module === module))
        .sort((a, b) => ORDRE[a.niveau] - ORDRE[b.niveau]),
    [projet.resultats.controles, niveau, module],
  );
  const compte = (n: Niveau) => projet.resultats.controles.filter((c) => c.niveau === n).length;

  async function expliquer(id: string) {
    setExplications((e) => ({ ...e, [id]: "chargement" }));
    try {
      const r = await api.expliquer(projet.id, id);
      setExplications((e) => ({ ...e, [id]: { texte: r.texte, source: r.source } }));
    } catch (err) {
      setExplications((e) => ({ ...e, [id]: { erreur: err instanceof ErreurApi ? err.message : "Explication indisponible." } }));
    }
  }

  return (
    <section>
      <h2>Rapport de conformité</h2>
      <div className="filtres">
        <label>
          Niveau
          <select value={niveau} onChange={(e) => setNiveau(e.target.value as Niveau | "tous")}>
            <option value="tous">Tous ({projet.resultats.controles.length})</option>
            <option value="bloquant">Bloquants ({compte("bloquant")})</option>
            <option value="avertissement">Avertissements ({compte("avertissement")})</option>
            <option value="ok">Conformes ({compte("ok")})</option>
          </select>
        </label>
        <label>
          Module
          <select value={module} onChange={(e) => setModule(e.target.value as Module | "tous")}>
            <option value="tous">Tous</option>
            {MODULES.map((m) => (
              <option key={m} value={m}>
                {LIBELLES_MODULES[m]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {controles.length === 0 && <p className="texte-2">Aucun contrôle pour ce filtre.</p>}
      <ul className="controles">
        {controles.map((c) => {
          const ex = explications[c.id];
          return (
            <li key={c.id} className={`controle controle-${c.niveau}`}>
              <div className="controle-tete">
                <Pastille statut={c.niveau} />
                <span className="mono petit">{c.id}</span>
                <strong>{c.titre}</strong>
              </div>
              <p>{c.detail}</p>
              <p className="texte-2 petit">
                {LIBELLES_MODULES[c.module]} · {c.reference_norme}
                {c.corrigeable && c.niveau === "bloquant" ? " · corrigeable en modifiant le programme" : ""}
              </p>
              {ex === undefined && (
                <button className="lien" onClick={() => expliquer(c.id)}>
                  Expliquer
                </button>
              )}
              {ex === "chargement" && <p className="texte-2">Explication en cours…</p>}
              {ex && typeof ex === "object" && "texte" in ex && (
                <blockquote className="explication">
                  {ex.texte}
                  <footer className="texte-2 petit">{ex.source === "ia" ? "Explication rédigée par l'IA, sans modifier aucune valeur" : "Texte du moteur de calcul"}</footer>
                </blockquote>
              )}
              {ex && typeof ex === "object" && "erreur" in ex && <p className="erreur-champ">{ex.erreur}</p>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
