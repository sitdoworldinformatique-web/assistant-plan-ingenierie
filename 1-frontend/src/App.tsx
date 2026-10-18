import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { aUnJeton, api, definirJeton, surDeconnexion } from "./api/client";
import { Chargement } from "./components/Etat";
import { naviguer, useRoute } from "./lib/routes";
import Connexion from "./pages/Connexion";
import type { Utilisateur } from "./types";

// Les pages lourdes sont chargées à la demande (connexions lentes)
const Projets = lazy(() => import("./pages/Projets"));
const Projet = lazy(() => import("./pages/Projet"));

function lireTheme(): string | null {
  try {
    return localStorage.getItem("theme");
  } catch {
    return null;
  }
}

export default function App() {
  const route = useRoute();
  const [utilisateur, setUtilisateur] = useState<Utilisateur | null>(null);
  const [verifie, setVerifie] = useState(!aUnJeton());
  const [theme, setTheme] = useState<string | null>(lireTheme);

  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }, [theme]);

  useEffect(() => {
    if (!aUnJeton()) return;
    api
      .moi()
      .then(setUtilisateur)
      .catch(() => definirJeton(null))
      .finally(() => setVerifie(true));
  }, []);

  useEffect(() => surDeconnexion(() => setUtilisateur(null)), []);

  const connecte = useCallback((u: Utilisateur, jeton: string) => {
    definirJeton(jeton);
    setUtilisateur(u);
    if (route.page === "connexion") naviguer({ page: "projets" }, true);
  }, [route.page]);

  const deconnecter = () => {
    definirJeton(null);
    setUtilisateur(null);
    naviguer({ page: "connexion" }, true);
  };

  const basculerTheme = () => {
    const sombre = theme ? theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    const suivant = sombre ? "light" : "dark";
    setTheme(suivant);
    try {
      localStorage.setItem("theme", suivant);
    } catch {
      /* préférence non mémorisée */
    }
  };

  if (!verifie) return <Chargement texte="Ouverture de la session…" />;
  if (!utilisateur) return <Connexion onConnecte={connecte} />;

  return (
    <div className="app">
      <header className="barre-haut">
        <a className="marque" href="#/projets">
          <span className="marque-logo" aria-hidden="true">◧</span> Assistant Plan Ingénierie
        </a>
        <nav className="barre-haut-actions">
          <span className="utilisateur" title={utilisateur.email}>
            {utilisateur.nom} · <span className="role">{utilisateur.role}</span>
          </span>
          <button className="bouton bouton-discret" onClick={basculerTheme}>
            Thème
          </button>
          <button className="bouton bouton-discret" onClick={deconnecter}>
            Déconnexion
          </button>
        </nav>
      </header>
      <Suspense fallback={<Chargement />}>
        {route.page === "projet" ? (
          <Projet key={route.id} id={route.id} onglet={route.onglet} utilisateur={utilisateur} />
        ) : route.page === "nouveau" ? (
          <Projet key="nouveau" utilisateur={utilisateur} />
        ) : (
          <Projets utilisateur={utilisateur} />
        )}
      </Suspense>
    </div>
  );
}
