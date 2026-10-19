import { type FormEvent, useState } from "react";
import { api, ErreurApi } from "../api/client";
import type { Utilisateur } from "../types";

export default function Connexion({ onConnecte }: { onConnecte: (u: Utilisateur, jeton: string) => void }) {
  const [mode, setMode] = useState<"connexion" | "inscription">("connexion");
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [nom, setNom] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function envoyer(e: FormEvent) {
    e.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      const s = mode === "connexion" ? await api.connexion(email, motDePasse) : await api.inscription(email, motDePasse, nom);
      onConnecte(s.utilisateur, s.jeton);
    } catch (err) {
      setErreur(err instanceof ErreurApi ? err.message : "Erreur inattendue.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <main className="page-connexion">
      <div className="carte carte-connexion">
        <h1>Assistant Plan Ingénierie</h1>
        <p className="texte-2">Décrivez la maison, les moteurs calculent, l'ingénieur valide et signe.</p>
        <div className="bascule" role="tablist" aria-label="Mode">
          <button role="tab" aria-selected={mode === "connexion"} className={mode === "connexion" ? "actif" : ""} onClick={() => setMode("connexion")}>
            Connexion
          </button>
          <button role="tab" aria-selected={mode === "inscription"} className={mode === "inscription" ? "actif" : ""} onClick={() => setMode("inscription")}>
            Créer un compte
          </button>
        </div>
        <form onSubmit={envoyer} className="formulaire">
          {mode === "inscription" && (
            <label>
              Nom complet
              <input value={nom} onChange={(e) => setNom(e.target.value)} required autoComplete="name" />
            </label>
          )}
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              value={motDePasse}
              onChange={(e) => setMotDePasse(e.target.value)}
              required
              minLength={mode === "inscription" ? 8 : undefined}
              autoComplete={mode === "connexion" ? "current-password" : "new-password"}
            />
            {mode === "inscription" && <span className="aide">8 caractères au minimum.</span>}
          </label>
          {erreur && (
            <p className="message-erreur" role="alert">
              {erreur}
            </p>
          )}
          <button className="bouton bouton-principal" type="submit" disabled={enCours}>
            {enCours ? "Un instant…" : mode === "connexion" ? "Se connecter" : "Créer le compte"}
          </button>
        </form>
      </div>
    </main>
  );
}
