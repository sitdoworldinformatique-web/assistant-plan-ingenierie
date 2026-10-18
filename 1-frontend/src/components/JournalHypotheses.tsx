import { dateHeure, nombre } from "../lib/format";
import { LIBELLES_MODULES, MODULES, type Projet } from "../types";

export default function JournalHypotheses({ projet }: { projet: Projet }) {
  const h = projet.resultats.hypotheses;
  return (
    <>
      <section>
        <h2>Hypothèses de calcul</h2>
        {MODULES.filter((m) => h.some((x) => x.module === m)).map((m) => (
          <details key={m} className="hypotheses">
            <summary>
              {LIBELLES_MODULES[m]} <span className="texte-2">({h.filter((x) => x.module === m).length})</span>
            </summary>
            <table className="tableau">
              <thead>
                <tr>
                  <th>Hypothèse</th>
                  <th>Valeur</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {h
                  .filter((x) => x.module === m)
                  .map((x, i) => (
                    <tr key={i}>
                      <td>{x.libelle}</td>
                      <td className="mono">{x.valeur}</td>
                      <td className="texte-2 petit">{x.source}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        ))}
        <p className="texte-2 petit">
          Moteurs de calcul version {projet.version_moteurs} · empreinte <span className="mono">{projet.empreinte.slice(0, 12)}…</span>
        </p>
      </section>
      <section>
        <h2>Journal IA</h2>
        {projet.journal_ia.length === 0 ? (
          <p className="texte-2">Aucune étape IA (programme saisi directement).</p>
        ) : (
          <div className="defilement-x">
            <table className="tableau">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Étape</th>
                  <th>Modèle</th>
                  <th>Résultat</th>
                  <th className="nombre">Durée</th>
                </tr>
              </thead>
              <tbody>
                {projet.journal_ia.map((e, i) => (
                  <tr key={i} className={e.erreur ? "ligne-erreur" : ""}>
                    <td className="petit">{dateHeure(e.date)}</td>
                    <td>
                      {e.etape}
                      {e.tentative ? ` (essai ${e.tentative})` : ""}
                      {e.iteration ? ` (itération ${e.iteration})` : ""}
                    </td>
                    <td className="mono petit">{e.modele}</td>
                    <td className="petit">{e.sortie_resume}</td>
                    <td className="nombre">{nombre(e.duree_ms / 1000, 1)} s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
