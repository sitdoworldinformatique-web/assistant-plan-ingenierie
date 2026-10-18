// Navigation par fragment d'URL (#/projets/12), sans bibliothèque de routage.
import { useEffect, useState } from "react";

export type Route =
  | { page: "connexion" }
  | { page: "projets" }
  | { page: "nouveau" }
  | { page: "admin" }
  | { page: "projet"; id: number; onglet?: string };

export function lireRoute(hash: string): Route {
  const morceaux = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (morceaux[0] === "connexion") return { page: "connexion" };
  if (morceaux[0] === "admin") return { page: "admin" };
  if (morceaux[0] === "projets" && morceaux[1] === "nouveau") return { page: "nouveau" };
  if (morceaux[0] === "projets" && morceaux[1] && /^\d+$/.test(morceaux[1])) {
    return { page: "projet", id: Number(morceaux[1]), onglet: morceaux[2] };
  }
  return { page: "projets" };
}

export function lienRoute(r: Route): string {
  switch (r.page) {
    case "connexion":
      return "#/connexion";
    case "projets":
      return "#/projets";
    case "nouveau":
      return "#/projets/nouveau";
    case "admin":
      return "#/admin";
    case "projet":
      return `#/projets/${r.id}${r.onglet ? "/" + r.onglet : ""}`;
  }
}

export function naviguer(r: Route, remplacer = false): void {
  const lien = lienRoute(r);
  if (remplacer) history.replaceState(null, "", lien);
  else history.pushState(null, "", lien);
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => lireRoute(location.hash));
  useEffect(() => {
    const f = () => setRoute(lireRoute(location.hash));
    window.addEventListener("hashchange", f);
    window.addEventListener("popstate", f);
    return () => {
      window.removeEventListener("hashchange", f);
      window.removeEventListener("popstate", f);
    };
  }, []);
  return route;
}
