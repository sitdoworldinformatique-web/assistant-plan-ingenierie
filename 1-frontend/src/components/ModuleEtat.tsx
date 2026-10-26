import { LIBELLES_MODULES, type Module, type Projet } from "../types";
import { Pastille } from "./Etat";

/** En-tête commun d'un onglet de module : statut, points à traiter, hypothèses, signature. */
export default function ModuleEtat({ projet, module }: { projet: Projet; module: Module }) {
  const controles = projet.resultats.controles.filter((c) => c.module === module && c.niveau !== "ok");
  const hypotheses = projet.resultats.hypotheses.filter((h) => h.module === module);
  const signe = projet.validations.find((v) => v.module === module && v.encore_valide);
  return (
    <section className="module-etat">
      <div className="module-etat-tete">
        <h2>{LIBELLES_MODULES[module]}</h2>
        <Pastille statut={projet.resultats.statuts_modules[module]} />
        {signe ? (
          <span className="pastille pastille-ok">
            <span className="pastille-point" aria-hidden="true" />
            Signé par {signe.nom}
          </span>
        ) : (
          <span className="mention-validation">À valider par un ingénieur qualifié</span>
        )}
      </div>
      {controles.length > 0 && (
        <ul className="points-module">
          {controles.map((c) => (
            <li key={c.id} className={`controle-${c.niveau}`}>
              <Pastille statut={c.niveau} /> <strong>{c.titre}</strong> — {c.detail}
            </li>
          ))}
        </ul>
      )}
      {hypotheses.length > 0 && (
        <details className="hypotheses">
          <summary>Hypothèses de calcul ({hypotheses.length})</summary>
          <table className="tableau">
            <tbody>
              {hypotheses.map((h, i) => (
                <tr key={i}>
                  <td>{h.libelle}</td>
                  <td className="mono">{h.valeur}</td>
                  <td className="texte-2 petit">{h.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  );
}
