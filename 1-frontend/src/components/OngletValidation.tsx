import type { Projet, Utilisateur } from "../types";
import JournalHypotheses from "./JournalHypotheses";
import RapportValidation from "./RapportValidation";
import Signature from "./Signature";

export default function OngletValidation({ projet, utilisateur, onSigne }: { projet: Projet; utilisateur: Utilisateur; onSigne: () => void }) {
  return (
    <div className="onglet-validation">
      <Signature projet={projet} utilisateur={utilisateur} onSigne={onSigne} />
      <RapportValidation projet={projet} />
      <JournalHypotheses projet={projet} />
    </div>
  );
}
