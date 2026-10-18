import { metres, nombre, pourcent, surface } from "../lib/format";
import type { Projet } from "../types";
import ModuleEtat from "./ModuleEtat";

export default function Toiture({ projet }: { projet: Projet }) {
  const t = projet.resultats.toiture;
  const terrasse = t.type === "terrasse";
  const lignes: [string, string][] = terrasse
    ? [
        ["Type", t.type],
        ["Couverture", t.couverture],
        ["Surface de dalle", surface(t.surface)],
        ["Volume de béton de dalle", `${nombre(t.dalle_volume)} m³`],
        ["Acrotère", metres(t.acrotere_ml)],
        ["Descentes d'eaux pluviales", nombre(t.descentes, 0)],
      ]
    : [
        ["Type", t.type],
        ["Couverture", t.couverture],
        ["Pente", pourcent(t.pente, 0)],
        ["Débord", metres(t.debord)],
        ["Surface en plan (débords compris)", surface(t.surface_plan)],
        ["Surface rampante", surface(t.surface)],
        ["Fermes", nombre(t.fermes, 0)],
        ["Bois des fermes", metres(t.longueur_fermes_ml, 1)],
        ["Pannes", metres(t.pannes_ml, 1)],
        ...(t.liteaux_ml ? ([["Liteaux", metres(t.liteaux_ml, 1)]] as [string, string][]) : []),
        ...(t.aretiers_ml ? ([["Arêtiers", metres(t.aretiers_ml, 1)]] as [string, string][]) : []),
        ["Faîtage", metres(t.faitage_ml, 1)],
        ["Total de charpente", metres(t.charpente_ml, 1)],
        ["Gouttières", metres(t.gouttieres, 1)],
        ["Descentes d'eaux pluviales", nombre(t.descentes, 0)],
      ];
  return (
    <div className="onglet-module">
      <ModuleEtat projet={projet} module="toiture" />
      <section>
        <h2>Quantités de toiture</h2>
        <table className="tableau tableau-cle-valeur">
          <tbody>
            {lignes.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td className="nombre">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
