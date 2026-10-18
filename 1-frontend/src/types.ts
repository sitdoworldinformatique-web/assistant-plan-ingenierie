// Types des données échangées avec l'API (miroir des modèles Pydantic du backend).

export type Niveau = "ok" | "avertissement" | "bloquant";
export type Statut = "conforme" | "conforme_avec_reserves" | "bloque";
export type Role = "constructeur" | "ingenieur" | "admin";
export type Module = "implantation" | "electricite" | "structure" | "toiture" | "solaire" | "metre";

export const MODULES: Module[] = ["implantation", "electricite", "structure", "toiture", "solaire", "metre"];
export const LIBELLES_MODULES: Record<Module, string> = {
  implantation: "Plan et implantation",
  electricite: "Électricité",
  structure: "Structure et fondations",
  toiture: "Toiture",
  solaire: "Solaire",
  metre: "Métré et devis",
};

export interface Utilisateur {
  id: number;
  email: string;
  nom: string;
  role: Role;
  numero_ordre?: string | null;
}

export interface Programme {
  nom: string;
  niveaux: number;
  chambres: number;
  salles_de_bain: number;
  wc_separe: boolean;
  bureau: boolean;
  garage: boolean;
  veranda: boolean;
  cuisine_ouverte: boolean;
  surface_sejour: number;
  terrain_largeur: number;
  terrain_profondeur: number;
  recul: number;
  hauteur_sous_plafond: number;
  toiture: "2 pans" | "4 pans" | "terrasse";
  couverture: "tole bac acier" | "tole ondulee" | "tuiles" | "dalle beton";
  pente_toiture: number;
  maconnerie: "parpaing 20" | "parpaing 15" | "brique";
  portance_sol: number;
  portance_mesuree: boolean;
  clim_chambres: boolean;
  clim_sejour: boolean;
  equipements: string[];
  resistance_terre: number | null;
  solaire: boolean;
  autonomie_h: number;
  ensoleillement_h: number;
  devise: string;
  longueurs_circuits: Record<string, number>;
}

export interface Controle {
  id: string;
  module: Module;
  niveau: Niveau;
  titre: string;
  detail: string;
  reference_norme: string;
  corrigeable: boolean;
}

export interface Hypothese {
  module: Module;
  libelle: string;
  valeur: string;
  source: string;
}

export interface Rect {
  x: number;
  y: number;
  l: number;
  p: number;
}

export interface Piece {
  id: string;
  type: string;
  nom: string;
  axe: Rect;
  net: Rect;
  surface_nette: number;
  habitable: boolean;
  exterieure: boolean;
}

export interface Circuit {
  key: string;
  cat: string;
  nom: string;
  det: string;
  n: number;
  unite: string;
  p: number;
  in_: number;
  s0: number;
  s: number;
  ks: number;
  lim: number;
  ib: number;
  l: number;
  du0: number;
  du: number;
  iz: number;
  etat: string;
  type_a: boolean;
  num: number;
  id: string;
}

export interface Differentiel {
  nom: string;
  type: string;
  circuits: string[];
  i: number;
  in_: number;
}

export interface Bilan {
  surface: number;
  p_installee: number;
  p_demandee: number;
  kva: number;
  i_abonnement: number;
  branchement: number;
}

// Résultats des modules suivis seulement en partie côté interface (le reste est affiché tel quel)
export interface Resultats {
  implantation: { pieces: Piece[]; emprise: Record<string, unknown>; parametres: Record<string, unknown> };
  electricite: { circuits: Circuit[]; differentiels: Differentiel[]; bilan: Bilan };
  structure: Record<string, unknown>;
  toiture: Record<string, unknown>;
  solaire: Record<string, unknown>;
  metre: Record<string, unknown>;
  controles: Controle[];
  hypotheses: Hypothese[];
  statut: Statut;
  statuts_modules: Record<Module, Statut>;
  version_moteurs: string;
}

export interface EntreeJournal {
  date: string;
  etape: string;
  entree_resume: string;
  sortie_resume: string;
  modele: string;
  duree_ms: number;
  erreur?: boolean;
  tentative?: number;
  iteration?: number;
}

export interface Validation {
  id: number;
  module: Module;
  ingenieur_id: number;
  nom: string;
  numero_ordre: string | null;
  empreinte: string;
  date: string;
  commentaire: string;
  encore_valide: boolean;
}

export interface Correction {
  iteration: number;
  explication: string;
  champs_modifies: string[];
  avant: Record<string, unknown>;
  apres: Record<string, unknown>;
}

export interface ResumeProjet {
  id: number;
  nom: string;
  statut: Statut;
  cree_le: string;
  modifie_le: string;
  proprietaire_id: number;
  version: number;
}

export interface Projet extends ResumeProjet {
  texte_initial: string;
  programme: Programme;
  resultats: Resultats;
  empreinte: string;
  journal_ia: EntreeJournal[];
  remarques: string[];
  version_moteurs: string;
  validations: Validation[];
  corrections?: Correction[];
}

export interface Sante {
  etat: string;
  version_moteurs: string;
  ia_texte_configuree: boolean;
  ia_image_configuree: boolean;
}
