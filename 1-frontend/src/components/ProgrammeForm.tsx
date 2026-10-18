import { type FormEvent, useEffect, useState } from "react";
import { lireNombre, nombre } from "../lib/format";
import type { Programme } from "../types";

type Champ =
  | { cle: keyof Programme; libelle: string; type: "nombre"; unite?: string; entier?: boolean; min?: number; max?: number; vide?: boolean; aide?: string }
  | { cle: keyof Programme; libelle: string; type: "case"; aide?: string }
  | { cle: keyof Programme; libelle: string; type: "choix"; options: string[] }
  | { cle: keyof Programme; libelle: string; type: "texte" };

const GROUPES: { titre: string; champs: Champ[] }[] = [
  {
    titre: "Général",
    champs: [
      { cle: "nom", libelle: "Nom", type: "texte" },
      { cle: "niveaux", libelle: "Niveaux", type: "nombre", entier: true, min: 1, max: 10, aide: "Seul le plain-pied (1) est pris en charge." },
    ],
  },
  {
    titre: "Pièces",
    champs: [
      { cle: "chambres", libelle: "Chambres", type: "nombre", entier: true, min: 0, max: 8 },
      { cle: "salles_de_bain", libelle: "Salles de bain", type: "nombre", entier: true, min: 1, max: 4 },
      { cle: "surface_sejour", libelle: "Surface du séjour", type: "nombre", unite: "m²", min: 0, aide: "0 = automatique" },
      { cle: "wc_separe", libelle: "WC séparé", type: "case" },
      { cle: "cuisine_ouverte", libelle: "Cuisine ouverte", type: "case" },
      { cle: "bureau", libelle: "Bureau", type: "case" },
      { cle: "garage", libelle: "Garage", type: "case" },
      { cle: "veranda", libelle: "Véranda", type: "case" },
    ],
  },
  {
    titre: "Terrain (données de site)",
    champs: [
      { cle: "terrain_largeur", libelle: "Largeur du terrain", type: "nombre", unite: "m", min: 1 },
      { cle: "terrain_profondeur", libelle: "Profondeur du terrain", type: "nombre", unite: "m", min: 1 },
      { cle: "recul", libelle: "Recul aux limites", type: "nombre", unite: "m", min: 0 },
      { cle: "portance_sol", libelle: "Portance du sol", type: "nombre", unite: "MPa", min: 0 },
      { cle: "portance_mesuree", libelle: "Portance mesurée (étude de sol)", type: "case", aide: "Sinon, hypothèse prudente." },
      { cle: "resistance_terre", libelle: "Résistance de la prise de terre", type: "nombre", unite: "Ω", min: 0, vide: true, aide: "Mesurée sur site ; vide si inconnue." },
    ],
  },
  {
    titre: "Construction",
    champs: [
      { cle: "hauteur_sous_plafond", libelle: "Hauteur sous plafond", type: "nombre", unite: "m", min: 2.2 },
      { cle: "maconnerie", libelle: "Maçonnerie", type: "choix", options: ["parpaing 20", "parpaing 15", "brique"] },
      { cle: "toiture", libelle: "Toiture", type: "choix", options: ["2 pans", "4 pans", "terrasse"] },
      { cle: "couverture", libelle: "Couverture", type: "choix", options: ["tole bac acier", "tole ondulee", "tuiles", "dalle beton"] },
      { cle: "pente_toiture", libelle: "Pente de toiture", type: "nombre", unite: "%", min: 0 },
    ],
  },
  {
    titre: "Équipements et énergie",
    champs: [
      { cle: "clim_chambres", libelle: "Climatisation des chambres", type: "case" },
      { cle: "clim_sejour", libelle: "Climatisation du séjour", type: "case" },
      { cle: "solaire", libelle: "Installation solaire", type: "case" },
      { cle: "autonomie_h", libelle: "Autonomie sur batteries", type: "nombre", unite: "h", min: 0 },
      { cle: "ensoleillement_h", libelle: "Ensoleillement", type: "nombre", unite: "h/j", min: 0 },
      { cle: "devise", libelle: "Devise", type: "texte" },
    ],
  },
];

const EQUIPEMENTS = [
  { id: "plaque", libelle: "Plaque de cuisson" },
  { id: "four", libelle: "Four" },
  { id: "lavelinge", libelle: "Lave-linge" },
  { id: "lavevaisselle", libelle: "Lave-vaisselle" },
  { id: "chauffeeau", libelle: "Chauffe-eau" },
  { id: "pompe", libelle: "Pompe" },
];

interface Props {
  programme: Programme;
  enCours: boolean;
  aDesSignatures: boolean;
  onRecalculer: (p: Programme) => void;
}

export default function ProgrammeForm({ programme, enCours, aDesSignatures, onRecalculer }: Props) {
  const [valeurs, setValeurs] = useState<Programme>(programme);
  const [saisies, setSaisies] = useState<Record<string, string>>({});
  const [erreurs, setErreurs] = useState<Record<string, string>>({});
  useEffect(() => {
    setValeurs(programme);
    setSaisies({});
    setErreurs({});
  }, [programme]);

  const modifie = JSON.stringify(valeurs) !== JSON.stringify(programme);

  function saisirNombre(c: Extract<Champ, { type: "nombre" }>, texte: string) {
    setSaisies((s) => ({ ...s, [c.cle]: texte }));
    if (c.vide && texte.trim() === "") {
      setValeurs((v) => ({ ...v, [c.cle]: null }));
      setErreurs(({ [c.cle]: _, ...e }) => e);
      return;
    }
    const n = lireNombre(texte);
    let err = "";
    if (n === null) err = "Nombre attendu.";
    else if (c.entier && !Number.isInteger(n)) err = "Nombre entier attendu.";
    else if (c.min !== undefined && n < c.min) err = `Minimum ${nombre(c.min, c.entier ? 0 : 2)}.`;
    else if (c.max !== undefined && n > c.max) err = `Maximum ${nombre(c.max, 0)}.`;
    setErreurs(({ [c.cle]: _, ...e }) => (err ? { ...e, [c.cle]: err } : e));
    if (!err && n !== null) setValeurs((v) => ({ ...v, [c.cle]: n }));
  }

  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    if (Object.keys(erreurs).length) return;
    if (aDesSignatures && !confirm("Modifier le programme annule les signatures de l'ingénieur. Continuer ?")) return;
    onRecalculer(valeurs);
  };

  return (
    <form className="programme" onSubmit={envoyer}>
      {GROUPES.map((g) => (
        <fieldset key={g.titre} className="groupe">
          <legend>{g.titre}</legend>
          {g.champs.map((c) => {
            const id = `prog-${c.cle}`;
            const v = valeurs[c.cle];
            if (c.type === "case")
              return (
                <label key={c.cle} className="case">
                  <input id={id} type="checkbox" checked={Boolean(v)} onChange={(e) => setValeurs((x) => ({ ...x, [c.cle]: e.target.checked }))} />
                  {c.libelle}
                  {c.aide && <span className="aide"> {c.aide}</span>}
                </label>
              );
            return (
              <div key={c.cle} className="champ">
                <label htmlFor={id}>
                  {c.libelle}
                  {c.type === "nombre" && c.unite ? ` (${c.unite})` : ""}
                </label>
                {c.type === "choix" ? (
                  <select id={id} value={String(v)} onChange={(e) => setValeurs((x) => ({ ...x, [c.cle]: e.target.value }))}>
                    {c.options.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : c.type === "texte" ? (
                  <input id={id} value={String(v ?? "")} onChange={(e) => setValeurs((x) => ({ ...x, [c.cle]: e.target.value }))} />
                ) : (
                  <input
                    id={id}
                    inputMode={c.entier ? "numeric" : "decimal"}
                    value={saisies[c.cle] ?? (v === null ? "" : nombre(v as number, c.entier ? 0 : 2).replace(/ /g, ""))}
                    onChange={(e) => saisirNombre(c, e.target.value)}
                    aria-invalid={Boolean(erreurs[c.cle])}
                    aria-describedby={erreurs[c.cle] ? `${id}-err` : undefined}
                  />
                )}
                {erreurs[c.cle] && (
                  <span id={`${id}-err`} className="erreur-champ">
                    {erreurs[c.cle]}
                  </span>
                )}
                {"aide" in c && c.aide && <span className="aide">{c.aide}</span>}
              </div>
            );
          })}
          {g.titre.startsWith("Équipements") && (
            <fieldset className="sous-groupe">
              <legend>Équipements spécialisés</legend>
              {EQUIPEMENTS.map((e) => (
                <label key={e.id} className="case">
                  <input
                    type="checkbox"
                    checked={valeurs.equipements.includes(e.id)}
                    onChange={(ev) =>
                      setValeurs((x) => ({
                        ...x,
                        equipements: ev.target.checked ? [...x.equipements, e.id] : x.equipements.filter((q) => q !== e.id),
                      }))
                    }
                  />
                  {e.libelle}
                </label>
              ))}
            </fieldset>
          )}
        </fieldset>
      ))}
      <div className="actions-collantes">
        <button className="bouton" type="button" disabled={!modifie || enCours} onClick={() => setValeurs(programme)}>
          Annuler les modifications
        </button>
        <button className="bouton bouton-principal" type="submit" disabled={!modifie || enCours || Object.keys(erreurs).length > 0}>
          {enCours ? "Recalcul…" : "Recalculer"}
        </button>
      </div>
    </form>
  );
}
