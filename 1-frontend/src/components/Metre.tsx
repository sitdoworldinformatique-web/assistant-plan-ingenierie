import { nombre } from "../lib/format";
import { api } from "../api/client";
import { nomFichier, telecharger } from "../lib/telecharger";
import type { LigneMetre, Projet } from "../types";
import ModuleEtat from "./ModuleEtat";

function prix(v: number, devise: string) {
  return `${nombre(v, 2)} ${devise === "USD" ? "$" : devise}`;
}

/** Export CSV (séparateur « ; », virgule décimale) en attendant le classeur XLSX du lot 10. */
function versCsv(lignes: LigneMetre[], total: number, devise: string): string {
  const champ = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const n = (v: number) => v.toFixed(2).replace(".", ",");
  const corps = lignes.map((l) => [champ(l.lot), champ(l.poste), n(l.quantite), champ(l.unite), n(l.prix_unitaire), n(l.total)].join(";"));
  return ["﻿Lot;Poste;Quantité;Unité;Prix unitaire (" + devise + ");Total (" + devise + ")", ...corps, `;;;;Total;${n(total)}`].join("\r\n");
}

export default function Metre({ projet, enCours, onRecalculer }: { projet: Projet; enCours: boolean; onRecalculer?: () => void }) {
  const m = projet.resultats.metre;
  const lots = [...new Set(m.lignes.map((l) => l.lot))];
  return (
    <div className="onglet-module">
      <ModuleEtat projet={projet} module="metre" />
      <section>
        <div className="entete-section">
          <h2>Métré et devis estimatif</h2>
          <div className="actions">
            {onRecalculer && (
              <button className="bouton" onClick={onRecalculer} disabled={enCours} title="Les signatures ne sont pas annulées : le programme ne change pas">
                {enCours ? "Recalcul…" : "Appliquer les prix actuels"}
              </button>
            )}
            <button className="bouton" onClick={() => telecharger(versCsv(m.lignes, m.total, m.devise), nomFichier(projet.nom + "-metre", "csv"), "text/csv;charset=utf-8")}>
              Exporter (CSV)
            </button>
            <button className="bouton" onClick={async () => telecharger(await api.exporter(projet.id, "metre.xlsx"), nomFichier(projet.nom + "-metre", "xlsx"))}>
              Exporter (XLSX)
            </button>
          </div>
        </div>
        <p className="mention-prix">Prix {m.mention_prix}.</p>
        <div className="defilement-x">
          <table className="tableau">
            <thead>
              <tr>
                <th>Poste</th>
                <th className="nombre">Quantité</th>
                <th>Unité</th>
                <th className="nombre">Prix unitaire</th>
                <th className="nombre">Total</th>
              </tr>
            </thead>
            {lots.map((lot) => {
              const lignes = m.lignes.filter((l) => l.lot === lot);
              const sousTotal = lignes.reduce((a, l) => a + l.total, 0);
              return (
                <tbody key={lot}>
                  <tr className="ligne-groupe">
                    <th colSpan={4}>{lot}</th>
                    <th className="nombre">{prix(sousTotal, m.devise)}</th>
                  </tr>
                  {lignes.map((l) => (
                    <tr key={l.code}>
                      <td>{l.poste}</td>
                      <td className="nombre">{nombre(l.quantite, Number.isInteger(l.quantite) || l.quantite >= 100 ? 0 : 2)}</td>
                      <td>{l.unite}</td>
                      <td className="nombre">{prix(l.prix_unitaire, m.devise)}</td>
                      <td className="nombre">{prix(l.total, m.devise)}</td>
                    </tr>
                  ))}
                </tbody>
              );
            })}
            <tfoot>
              <tr className="ligne-total">
                <th colSpan={4}>Total estimatif</th>
                <th className="nombre">{prix(m.total, m.devise)}</th>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  );
}
