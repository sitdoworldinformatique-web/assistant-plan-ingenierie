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

export interface Semelle {
  id: string;
  mur_id: string;
  longueur: number;
  largeur_reprise: number;
  q_mur: number;
  q_chainage: number;
  q_toiture: number;
  q_els: number;
  largeur: number;
  hauteur: number;
  ferraillage: string;
}

export interface Poteau {
  id: string;
  x: number;
  y: number;
  section: string;
  armatures: string;
  cadres: string;
  motif: string;
}

export interface Chainage {
  id: string;
  type: string;
  reference: string;
  longueur: number;
  section: string;
}

export interface Structure {
  semelles: Semelle[];
  poteaux: Poteau[];
  chainages: Chainage[];
  dallage: { surface: number; epaisseur: number; herisson: number; treillis: string; volume_beton: number };
  hauteur_mur: number;
}

export interface Toiture {
  type: string;
  couverture: string;
  pente: number;
  surface_plan: number;
  surface: number;
  debord: number;
  fermes: number;
  longueur_fermes_ml: number;
  pannes_ml: number;
  liteaux_ml: number;
  aretiers_ml: number;
  faitage_ml: number;
  charpente_ml: number;
  gouttieres: number;
  descentes: number;
  dalle_volume: number;
  acrotere_ml: number;
}

export interface Solaire {
  demande: boolean;
  charges_essentielles_w: number;
  onduleur_kva: number;
  batteries_kwh: number;
  energie_jour_kwh: number;
  panneaux_kwc: number;
}

export interface LigneMetre {
  lot: string;
  code: string;
  poste: string;
  quantite: number;
  unite: string;
  prix_unitaire: number;
  total: number;
}

export interface Metre {
  lignes: LigneMetre[];
  total: number;
  devise: string;
  mention_prix: string;
  quantites: Record<string, number>;
}

export interface PrixMateriau {
  code: string;
  libelle: string;
  unite: string;
  prix: number;
  devise: string;
  mis_a_jour_le: string;
}

export interface Resultats {
  implantation: { pieces: Piece[]; emprise: Record<string, unknown>; parametres: Record<string, unknown> };
  electricite: { circuits: Circuit[]; differentiels: Differentiel[]; bilan: Bilan; points: { piece_id: string; type: string }[] };
  structure: Structure;
  toiture: Toiture;
  solaire: Solaire;
  metre: Metre;
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
