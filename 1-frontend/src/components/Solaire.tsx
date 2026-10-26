import { nombre } from "../lib/format";
import type { Projet } from "../types";
import ModuleEtat from "./ModuleEtat";

export default function Solaire({ projet }: { projet: Projet }) {
  const s = projet.resultats.solaire;
  return (
    <div className="onglet-module">
      <ModuleEtat projet={projet} module="solaire" />
      {!s.demande ? (
        <p className="texte-2">Pas d'installation solaire dans le programme. Cochez « Installation solaire » dans l'onglet Programme pour la prédimensionner.</p>
      ) : (
        <section>
          <h2>Prédimensionnement du kit solaire</h2>
          <p className="texte-2 petit">
            Autonomie {nombre(projet.programme.autonomie_h, 0)} h · ensoleillement {nombre(projet.programme.ensoleillement_h, 1)} h/j. Valeurs à confirmer par un bilan
            de consommation détaillé.
          </p>
          <dl className="bilan">
            <div>
              <dt>Charges essentielles</dt>
              <dd>{nombre(s.charges_essentielles_w / 1000, 1)} kW</dd>
            </div>
            <div>
              <dt>Énergie par jour</dt>
              <dd>{nombre(s.energie_jour_kwh, 1)} kWh</dd>
            </div>
            <div>
              <dt>Onduleur</dt>
              <dd>{nombre(s.onduleur_kva, 1)} kVA</dd>
            </div>
            <div>
              <dt>Batteries</dt>
              <dd>{nombre(s.batteries_kwh, 1)} kWh</dd>
            </div>
            <div>
              <dt>Panneaux</dt>
              <dd>{nombre(s.panneaux_kwc, 2)} kWc</dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  );
}
