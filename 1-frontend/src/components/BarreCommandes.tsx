import { type FormEvent, useEffect, useRef, useState } from "react";
import type { EntreeJournal } from "../types";

const SUGGESTIONS = [
  "Ajoute une chambre",
  "Supprime la véranda",
  "Ajoute un garage",
  "Agrandis le séjour de 5 m²",
  "Toiture 4 pans en tuiles",
  "Toit terrasse",
  "Terrain 25 x 30",
  "Annule la dernière étape",
];

interface Echange {
  cle: string;
  texte: string;
  message: string;
  annulee: boolean;
  compris: boolean;
}

interface Props {
  journal: EntreeJournal[];
  texteInitial: string;
  enCours: boolean;
  peutModifier: boolean;
  /** Renvoie la réponse affichée si la commande n'a pas été comprise (elle n'est pas dans le journal). */
  onCommande: (texte: string) => Promise<{ comprise: boolean; message: string } | null>;
}

/** Conversation en étapes : chaque commande en français modifie la maison, les moteurs recalculent et répondent. */
export default function BarreCommandes({ journal, texteInitial, enCours, peutModifier, onCommande }: Props) {
  const [texte, setTexte] = useState("");
  const [incompris, setIncompris] = useState<Echange[]>([]);
  const fin = useRef<HTMLDivElement>(null);

  const echanges: Echange[] = journal
    .filter((e) => e.etape === "commande" && e.message)
    .map((e, i) => ({ cle: `j${i}`, texte: e.entree_resume, message: e.message ?? "", annulee: !!e.annulee, compris: true }));
  const tous = [...echanges, ...incompris];

  useEffect(() => {
    fin.current?.scrollIntoView?.({ block: "nearest" });
  }, [tous.length]);
  // Les réponses « non comprise » disparaissent dès qu'une commande est enregistrée
  useEffect(() => setIncompris([]), [journal.length]);

  async function envoyer(valeur: string) {
    const t = valeur.trim();
    if (!t || enCours) return;
    setTexte("");
    const r = await onCommande(t);
    if (r && !r.comprise) setIncompris((l) => [...l, { cle: `i${l.length}`, texte: t, message: r.message, annulee: false, compris: false }]);
  }
  const soumettre = (e: FormEvent) => {
    e.preventDefault();
    void envoyer(texte);
  };

  return (
    <section className="commandes" aria-label="Commandes en français">
      <h2>Décrire, puis préciser étape par étape</h2>
      <div className="echanges" role="log" aria-live="polite">
        {texteInitial && (
          <div className="echange">
            <p className="vous">{texteInitial}</p>
            <p className="reponse texte-2">Maison calculée à partir de cette description.</p>
          </div>
        )}
        {tous.map((e) => (
          <div className={`echange${e.annulee ? " annulee" : ""}`} key={e.cle}>
            <p className="vous">{e.texte}</p>
            <p className={`reponse${e.compris ? "" : " texte-2"}`}>{e.message}</p>
          </div>
        ))}
        <div ref={fin} />
      </div>
      {peutModifier ? (
        <>
          <form className="saisie-commande" onSubmit={soumettre}>
            <label className="visuellement-cache" htmlFor="commande">
              Commande
            </label>
            <input
              id="commande"
              value={texte}
              onChange={(e) => setTexte(e.target.value)}
              placeholder="Ex. : ajoute une chambre, toiture 4 pans en tuiles…"
              autoComplete="off"
              maxLength={1000}
              disabled={enCours}
            />
            <button className="bouton bouton-principal" disabled={enCours || !texte.trim()}>
              {enCours ? "Calcul…" : "Envoyer"}
            </button>
          </form>
          <div className="suggestions" aria-label="Suggestions de commandes">
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" className="puce" disabled={enCours} onClick={() => void envoyer(s)}>
                {s}
              </button>
            ))}
          </div>
        </>
      ) : (
        <p className="texte-2 petit">Ce projet est en lecture seule pour vous.</p>
      )}
    </section>
  );
}
