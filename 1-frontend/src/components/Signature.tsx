import { useState } from "react";
import { api, ErreurApi } from "../api/client";
import { dateHeure } from "../lib/format";
import { LIBELLES_MODULES, MODULES, type Module, type Projet, type Utilisateur } from "../types";
import { Pastille } from "./Etat";

interface Props {
  projet: Projet;
  utilisateur: Utilisateur;
  onSigne: () => void;
}

export default function Signature({ projet, utilisateur, onSigne }: Props) {
  const [commentaires, setCommentaires] = useState<Record<string, string>>({});
  const [enCours, setEnCours] = useState<Module | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);
  const ingenieur = utilisateur.role === "ingenieur";

  async function signer(m: Module) {
    setErreur(null);
    setEnCours(m);
    try {
      await api.valider(projet.id, m, commentaires[m] ?? "");
      onSigne();
    } catch (e) {
      setErreur(e instanceof ErreurApi ? e.message : "Signature impossible.");
    } finally {
      setEnCours(null);
    }
  }

  return (
    <section>
      <h2>Signature par module</h2>
      {!ingenieur && <p className="texte-2">Seul un ingénieur peut signer. Toute modification du programme annule les signatures.</p>}
      {erreur && (
        <p className="message-erreur" role="alert">
          {erreur}
        </p>
      )}
      <ul className="signatures">
        {MODULES.map((m) => {
          const statut = projet.resultats.statuts_modules[m];
          const valides = projet.validations.filter((v) => v.module === m && v.encore_valide);
          const anciennes = projet.validations.filter((v) => v.module === m && !v.encore_valide);
          const signe = valides[valides.length - 1];
          return (
            <li key={m} className="signature">
              <div className="signature-tete">
                <strong>{LIBELLES_MODULES[m]}</strong>
                <Pastille statut={statut} />
                {signe ? (
                  <span className="pastille pastille-ok">
                    <span className="pastille-point" aria-hidden="true" />
                    Signé
                  </span>
                ) : (
                  <span className="texte-2">À valider par un ingénieur qualifié</span>
                )}
              </div>
              {signe && (
                <p className="petit">
                  Signé par {signe.nom}
                  {signe.numero_ordre ? ` (n° ${signe.numero_ordre})` : ""} le {dateHeure(signe.date)}
                  {signe.commentaire ? ` — « ${signe.commentaire} »` : ""}
                </p>
              )}
              {!signe && anciennes.length > 0 && <p className="petit texte-2">Signature annulée par une modification du programme.</p>}
              {ingenieur && !signe && (
                <div className="signer">
                  <label className="visuellement-cache" htmlFor={`com-${m}`}>
                    Commentaire pour {LIBELLES_MODULES[m]}
                  </label>
                  <input
                    id={`com-${m}`}
                    placeholder="Commentaire (facultatif)"
                    value={commentaires[m] ?? ""}
                    onChange={(e) => setCommentaires((c) => ({ ...c, [m]: e.target.value }))}
                  />
                  <button className="bouton bouton-principal" disabled={statut === "bloque" || enCours !== null} onClick={() => signer(m)}>
                    {enCours === m ? "Signature…" : "Signer le module"}
                  </button>
                  {statut === "bloque" && <span className="texte-2 petit">Impossible tant qu'un point est bloquant.</span>}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
