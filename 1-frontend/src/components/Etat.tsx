import { LIBELLES_NIVEAU, LIBELLES_STATUT } from "../lib/format";
import type { Niveau, Statut } from "../types";

export function Chargement({ texte = "Chargement…" }: { texte?: string }) {
  return (
    <div className="chargement" role="status" aria-live="polite">
      <span className="roue" aria-hidden="true" /> {texte}
    </div>
  );
}

export function MessageErreur({ message, onReessayer }: { message: string; onReessayer?: () => void }) {
  return (
    <div className="message-erreur" role="alert">
      <span>{message}</span>
      {onReessayer && (
        <button className="bouton" onClick={onReessayer}>
          Réessayer
        </button>
      )}
    </div>
  );
}

const CLASSE: Record<string, string> = {
  conforme: "ok",
  ok: "ok",
  conforme_avec_reserves: "avertissement",
  avertissement: "avertissement",
  bloque: "bloquant",
  bloquant: "bloquant",
};

/** Pastille d'état : la couleur est toujours accompagnée d'un texte. */
export function Pastille({ statut, texte }: { statut: Statut | Niveau; texte?: string }) {
  const libelle = texte ?? LIBELLES_STATUT[statut] ?? LIBELLES_NIVEAU[statut] ?? statut;
  return (
    <span className={`pastille pastille-${CLASSE[statut] ?? "ok"}`}>
      <span className="pastille-point" aria-hidden="true" />
      {libelle}
    </span>
  );
}
