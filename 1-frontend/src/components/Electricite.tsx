import { useEffect, useState } from "react";
import { api } from "../api/client";
import { lireNombre, nombre } from "../lib/format";
import type { Circuit, Projet } from "../types";
import { Chargement, MessageErreur, Pastille } from "./Etat";

const ETATS: Record<string, { statut: "ok" | "avertissement" | "bloquant"; texte: string }> = {
  ok: { statut: "ok", texte: "Conforme" },
  warn: { statut: "avertissement", texte: "Section augmentée" },
  bad: { statut: "bloquant", texte: "Non conforme" },
};

interface Props {
  projet: Projet;
  enCours: boolean;
  onLongueurs: (longueurs: Record<string, number>) => void;
}

export default function Electricite({ projet, enCours, onLongueurs }: Props) {
  const elec = projet.resultats.electricite;
  const [saisies, setSaisies] = useState<Record<string, string>>({});
  const [unifilaire, setUnifilaire] = useState<string | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => setSaisies({}), [projet.empreinte]);
  useEffect(() => {
    setUnifilaire(null);
    api
      .unifilaireSvg(projet.id)
      .then(setUnifilaire)
      .catch(() => setErreur("Schéma unifilaire indisponible."));
  }, [projet.id, projet.empreinte]);

  const parKey = new Map(elec.circuits.map((c) => [c.key, c]));
  const invalides = Object.entries(saisies).filter(([, t]) => {
    const n = lireNombre(t);
    return n === null || n <= 0;
  });

  const appliquer = () => {
    const longueurs = { ...projet.programme.longueurs_circuits };
    for (const [k, t] of Object.entries(saisies)) {
      const n = lireNombre(t);
      if (n !== null && n > 0) longueurs[k] = n;
    }
    onLongueurs(longueurs);
  };
  const reinitialiser = (key: string) => {
    const { [key]: _, ...reste } = projet.programme.longueurs_circuits;
    onLongueurs(reste);
  };

  const ligne = (c: Circuit) => {
    const surcharge = c.key in projet.programme.longueurs_circuits;
    const e = ETATS[c.etat] ?? ETATS.ok;
    return (
      <tr key={c.key}>
        <th scope="row" className="mono">
          C{c.num}
        </th>
        <td>
          {c.nom}
          <div className="texte-2 petit">{c.det}</div>
        </td>
        <td className="nombre">
          {c.n} {c.unite}
        </td>
        <td className="nombre">{nombre(c.p, 0)} W</td>
        <td className="nombre">{c.in_} A</td>
        <td className="nombre">{nombre(c.s, 1)} mm²</td>
        <td className="nombre">
          <label className="visuellement-cache" htmlFor={`l-${c.key}`}>
            Longueur du circuit C{c.num} en mètres
          </label>
          <input
            id={`l-${c.key}`}
            className="champ-court"
            inputMode="decimal"
            value={saisies[c.key] ?? nombre(c.l, 1)}
            onChange={(ev) => setSaisies((s) => ({ ...s, [c.key]: ev.target.value }))}
            aria-invalid={c.key in saisies && invalides.some(([k]) => k === c.key)}
          />
          {surcharge && (
            <button className="lien petit" type="button" onClick={() => reinitialiser(c.key)} title="Revenir à la longueur estimée">
              estimée
            </button>
          )}
        </td>
        <td className="nombre">
          {nombre(c.du)} % <span className="texte-2">/ {nombre(c.lim, 0)} %</span>
        </td>
        <td>
          <Pastille statut={e.statut} texte={e.texte} />
          {c.type_a && <span className="etiquette">type A</span>}
        </td>
      </tr>
    );
  };

  return (
    <div className="onglet-elec">
      <section>
        <h2>Circuits par interrupteur différentiel</h2>
        <p className="texte-2">
          Les longueurs sont estimées depuis le plan (distance au tableau + 2 m, +10 %). Saisissez les longueurs réelles si vous les connaissez.
        </p>
        <div className="defilement-x">
          <table className="tableau">
            <thead>
              <tr>
                <th>N°</th>
                <th>Circuit</th>
                <th className="nombre">Points</th>
                <th className="nombre">Puissance</th>
                <th className="nombre">Protection</th>
                <th className="nombre">Section</th>
                <th className="nombre">Longueur (m)</th>
                <th className="nombre">Chute de tension</th>
                <th>État</th>
              </tr>
            </thead>
            {elec.differentiels.map((d) => (
              <tbody key={d.nom}>
                <tr className="ligne-groupe">
                  <th colSpan={9}>
                    {d.nom} · 30 mA type {d.type} · {d.in_} A <span className="texte-2">({nombre(d.i, 1)} A estimés)</span>
                  </th>
                </tr>
                {d.circuits.map((k) => parKey.get(k)).filter((c): c is Circuit => Boolean(c)).map(ligne)}
              </tbody>
            ))}
          </table>
        </div>
        <div className="actions">
          <button className="bouton bouton-principal" disabled={enCours || Object.keys(saisies).length === 0 || invalides.length > 0} onClick={appliquer}>
            {enCours ? "Recalcul…" : "Appliquer les longueurs"}
          </button>
          {invalides.length > 0 && <span className="erreur-champ">Longueur positive attendue.</span>}
        </div>
      </section>
      <section>
        <h2>Bilan de puissance</h2>
        <dl className="bilan">
          <div>
            <dt>Puissance installée</dt>
            <dd>{nombre(elec.bilan.p_installee / 1000, 1)} kW</dd>
          </div>
          <div>
            <dt>Puissance demandée</dt>
            <dd>{nombre(elec.bilan.p_demandee / 1000, 1)} kW</dd>
          </div>
          <div>
            <dt>Puissance apparente</dt>
            <dd>{nombre(elec.bilan.kva, 1)} kVA</dd>
          </div>
          <div>
            <dt>Courant d'abonnement</dt>
            <dd>{nombre(elec.bilan.i_abonnement, 1)} A</dd>
          </div>
          <div>
            <dt>Branchement conseillé</dt>
            <dd>{elec.bilan.branchement} A</dd>
          </div>
        </dl>
      </section>
      <section>
        <h2>Schéma unifilaire</h2>
        {erreur && <MessageErreur message={erreur} />}
        {!unifilaire && !erreur && <Chargement />}
        {unifilaire && <div className="unifilaire" dangerouslySetInnerHTML={{ __html: unifilaire }} />}
      </section>
    </div>
  );
}
