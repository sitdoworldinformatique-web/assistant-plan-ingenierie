// Client de l'API : jeton JWT, erreurs {code, message} en français, reprise sur coupure réseau.

import type { ListeRendus, Module, PrixMateriau, RenduIA, Programme, Projet, ResumeProjet, Role, Sante, Utilisateur, Validation } from "../types";

const CLE_JETON = "api.jeton";

export class ErreurApi extends Error {
  constructor(
    public statut: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

function lireJeton(): string | null {
  try {
    return localStorage.getItem(CLE_JETON);
  } catch {
    return null;
  }
}

let jeton: string | null = lireJeton();
const auditeurs = new Set<() => void>();

export function definirJeton(valeur: string | null): void {
  jeton = valeur;
  try {
    if (valeur) localStorage.setItem(CLE_JETON, valeur);
    else localStorage.removeItem(CLE_JETON);
  } catch {
    /* stockage indisponible : le jeton reste en mémoire */
  }
}

export const aUnJeton = () => jeton !== null;

/** Prévient l'application quand la session expire (401). */
export function surDeconnexion(f: () => void): () => void {
  auditeurs.add(f);
  return () => auditeurs.delete(f);
}

const attendre = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface Options {
  methode?: string;
  corps?: unknown;
  /** Nouvelles tentatives sur coupure réseau (lectures seulement, par défaut). */
  tentatives?: number;
  format?: "json" | "texte" | "blob";
}

export async function requete<T>(chemin: string, { methode = "GET", corps, tentatives, format = "json" }: Options = {}): Promise<T> {
  const essais = 1 + (tentatives ?? (methode === "GET" ? 2 : 0));
  const entetes: Record<string, string> = {};
  if (jeton) entetes.Authorization = `Bearer ${jeton}`;
  if (corps !== undefined) entetes["Content-Type"] = "application/json";
  let derniere: unknown;
  for (let n = 1; n <= essais; n++) {
    let r: Response;
    try {
      r = await fetch(chemin, { method: methode, headers: entetes, body: corps === undefined ? undefined : JSON.stringify(corps) });
    } catch (e) {
      derniere = e;
      if (n < essais) await attendre(800 * n);
      continue;
    }
    if (!r.ok) {
      let code = "erreur";
      let message = `Erreur ${r.status}.`;
      try {
        const j = await r.json();
        code = j.code ?? code;
        message = j.message ?? message;
      } catch {
        /* corps non JSON */
      }
      if (r.status === 401 && chemin !== "/api/auth/connexion") {
        definirJeton(null);
        auditeurs.forEach((f) => f());
      }
      if (r.status >= 502 && r.status <= 504 && n < essais) {
        await attendre(800 * n);
        continue;
      }
      throw new ErreurApi(r.status, code, message);
    }
    if (r.status === 204) return undefined as T;
    if (format === "texte") return (await r.text()) as T;
    if (format === "blob") return (await r.blob()) as T;
    return (await r.json()) as T;
  }
  void derniere;
  throw new ErreurApi(0, "reseau", "Connexion au serveur impossible. Vérifiez votre réseau puis réessayez.");
}

interface SessionUtilisateur {
  jeton: string;
  utilisateur: Utilisateur;
}

export const api = {
  sante: () => requete<Sante>("/api/sante"),
  inscription: (email: string, mot_de_passe: string, nom: string) =>
    requete<SessionUtilisateur>("/api/auth/inscription", { methode: "POST", corps: { email, mot_de_passe, nom } }),
  connexion: (email: string, mot_de_passe: string) =>
    requete<SessionUtilisateur>("/api/auth/connexion", { methode: "POST", corps: { email, mot_de_passe } }),
  moi: () => requete<Utilisateur>("/api/auth/moi"),
  projets: () => requete<ResumeProjet[]>("/api/projets"),
  projet: (id: number) => requete<Projet>(`/api/projets/${id}`),
  generer: (texte: string, projet_id?: number) =>
    requete<Projet>("/api/projets/generer", { methode: "POST", corps: { texte, projet_id } }),
  modifierProgramme: (id: number, programme: Programme) =>
    requete<Projet>(`/api/projets/${id}/programme`, { methode: "PUT", corps: programme }),
  supprimer: (id: number) => requete<void>(`/api/projets/${id}`, { methode: "DELETE" }),
  planSvg: (id: number, calques: string[]) =>
    requete<string>(`/api/projets/${id}/plan.svg?calques=${calques.join(",")}`, { format: "texte" }),
  unifilaireSvg: (id: number) => requete<string>(`/api/projets/${id}/unifilaire.svg`, { format: "texte" }),
  rapport: (id: number) => requete<string>(`/api/projets/${id}/rapport.txt`, { format: "texte" }),
  expliquer: (id: number, element_id: string) =>
    requete<{ element_id: string; texte: string; source: "ia" | "regles" }>(`/api/projets/${id}/expliquer`, {
      methode: "POST",
      corps: { element_id },
    }),
  validations: (id: number) =>
    requete<{ validations: Validation[]; modules: Record<Module, boolean> }>(`/api/projets/${id}/validations`),
  rendus: (id: number) => requete<ListeRendus>(`/api/projets/${id}/rendus`),
  creerRendu: (id: number, style: string, image_base64: string) =>
    requete<RenduIA>(`/api/projets/${id}/rendus`, { methode: "POST", corps: { style, image_base64 } }),
  imageRendu: (url: string) => requete<Blob>(url, { format: "blob" }),
  supprimerRendu: (id: number, rendu: number) => requete<void>(`/api/projets/${id}/rendus/${rendu}`, { methode: "DELETE" }),
  prix: () => requete<PrixMateriau[]>("/api/admin/prix"),
  modifierPrix: (entrees: { code: string; prix: number; libelle?: string; unite?: string; devise?: string }[]) =>
    requete<PrixMateriau[]>("/api/admin/prix", { methode: "PUT", corps: entrees }),
  utilisateurs: () => requete<Utilisateur[]>("/api/admin/utilisateurs"),
  modifierUtilisateur: (id: number, role: Role, numero_ordre: string | null) =>
    requete<Utilisateur>(`/api/admin/utilisateurs/${id}`, { methode: "PUT", corps: { role, numero_ordre } }),
  valider: (id: number, module: Module, commentaire: string) =>
    requete<Validation>(`/api/projets/${id}/validations`, { methode: "POST", corps: { module, commentaire } }),
};
