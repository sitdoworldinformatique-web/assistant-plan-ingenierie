"""Constantes normatives, groupées par référentiel.

Aucun moteur ne code une valeur normative en dur : tout passe par ce module.
Pour ajouter une norme locale, créer un nouveau groupe et le sélectionner ici,
sans toucher aux moteurs.
"""
from __future__ import annotations

VERSION_MOTEURS = "0.1.0"

# ---------------------------------------------------------------------------
# Implantation — règles de programmation (cahier des charges § 6.1)
# ---------------------------------------------------------------------------
IMPLANTATION = {
    "reference": "Règles de programmation internes (CdC § 6.1)",
    "profondeur_bande_nuit": 3.6,
    "largeur_couloir": 1.2,
    "profondeur_jour_min": 4.2,
    "profondeur_jour_max": 6.5,
    "surface_sejour_base": 20.0,
    "surface_sejour_par_chambre": 4.0,
    "surface_cuisine": 11.0,
    "surface_chambre_parentale": 14.0,
    "surface_chambre": 11.5,
    "surface_bureau": 9.0,
    "largeur_bloc_sanitaire": 3.0,
    "largeur_sdb": 1.9,
    "largeur_colonne_wc": 1.1,
    "profondeur_wc": 1.8,
    "largeur_garage": 3.2,
    "profondeur_veranda": 2.5,
    "largeur_sejour_min": 3.6,
    "epaisseur_mur_ext": {"parpaing 20": 0.20, "parpaing 15": 0.15, "brique": 0.20},
    "epaisseur_cloison": 0.10,
    # ouvertures (largeur, hauteur) en m
    "porte_entree": (0.90, 2.15),
    "porte_interieure": (0.80, 2.05),
    "porte_wc": (0.70, 2.05),
    "porte_garage": (2.40, 2.10),
    "baie_sejour_couloir": (1.40, 2.10),
    "baie_cuisine_ouverte": (2.00, 2.10),
    "ouverture_placard": (0.90, 2.05),
    "fenetre_chambre": (1.20, 1.35),
    "fenetre_sejour": (1.60, 2.15),
    "nb_fenetres_sejour": 2,
    "fenetre_cuisine": (1.20, 1.15),
    "fenetre_sdb": (0.60, 0.60),
    "fenetre_bureau": (1.20, 1.35),
    "distance_angle_ouverture": 0.15,
}

# Contrôles d'habitabilité
HABITABILITE = {
    "reference": "Règles d'habitabilité usuelles (surface minimale, éclairement naturel)",
    "surface_min_chambre": 9.0,
    "surface_min_sejour": 18.0,
    "largeur_min_couloir": 0.90,
    "ratio_eclairement": 1 / 6,
}

# ---------------------------------------------------------------------------
# Électricité — inspiré de la NF C 15-100 (logement, monophasé), simplifié
# ---------------------------------------------------------------------------
ELECTRICITE = {
    "reference": "NF C 15-100 (simplifiée, logement monophasé)",
    "tension": 230.0,
    "cos_phi": 0.9,
    "resistivite_cuivre": 0.023,  # Ω·mm²/m en service
    "limite_du_eclairage": 3.0,
    "limite_du_autres": 5.0,
    "sections": [1.5, 2.5, 4.0, 6.0, 10.0, 16.0],
    "iz": {1.5: 17.5, 2.5: 24.0, 4.0: 32.0, 6.0: 41.0, 10.0: 57.0, 16.0: 76.0},
    "eclairage": {"section": 1.5, "in": 16, "max_points": 8, "p_point": 100.0, "ks": 1.0},
    "prises": {"section": 2.5, "in": 20, "max_prises": 12, "ib": 16.0, "p_prise": 300.0, "ks": 0.25},
    "prises_cuisine": {"max_prises": 6, "ks": 0.3, "surface_seuil": 4.0, "nb_si_grande": 6, "nb_si_petite": 3},
    "specialises": {
        "plaque": {"libelle": "Plaque de cuisson", "p": 7200.0, "in": 32, "section": 6.0, "ks": 0.7, "type_a": True},
        "four": {"libelle": "Four", "p": 3000.0, "in": 20, "section": 2.5, "ks": 0.75, "type_a": False},
        "lavelinge": {"libelle": "Lave-linge", "p": 2500.0, "in": 20, "section": 2.5, "ks": 0.75, "type_a": True},
        "lavevaisselle": {"libelle": "Lave-vaisselle", "p": 2000.0, "in": 20, "section": 2.5, "ks": 0.75,
                          "type_a": False},
        "chauffeeau": {"libelle": "Chauffe-eau électrique", "p": 2000.0, "in": 20, "section": 2.5, "ks": 1.0,
                       "type_a": False},
        "pompe": {"libelle": "Pompe / surpresseur", "p": 1100.0, "in": 16, "section": 2.5, "ks": 1.0,
                  "type_a": False},
    },
    "ordre_specialises": ["plaque", "four", "lavelinge", "lavevaisselle", "chauffeeau", "pompe"],
    "clim": {"libelle": "Climatiseur", "p": 1200.0, "in": 20, "section": 2.5, "ks": 0.8},
    "max_circuits_par_id": 8,
    "id_seuils_surface": (35.0, 100.0),  # surface < 35 m² : 1 ID ; ≤ 100 m² : 2 ; au-delà : 3
    "id_calibres": (40, 63),
    "id_seuil_calibre": 40.0,
    "foisonnement": 0.6,
    "branchements": [15, 30, 45, 60],
    "differentiel_branchement_ma": 500,
    "terre_ok": 100.0,
    "terre_max": 500.0,
    "longueur_remontees": 2.0,
    "majoration_longueur": 0.10,
    "conducteurs_par_cable": 3,
    "distance_prise_angle": 0.30,
    # Règles par type de pièce : ("fixe", n) ; ("par_m2", m² par unité, minimum) ; ("seuil", m², n si >, n sinon)
    "regles_pieces": {
        "sejour": {"libelle": "Séjour / salon", "prises": ("par_m2", 4.0, 5), "lum": ("par_m2", 20.0, 1)},
        "chambre": {"libelle": "Chambre", "prises": ("fixe", 3), "lum": ("fixe", 1)},
        "cuisine": {"libelle": "Cuisine", "prises": ("seuil", 4.0, 6, 3), "lum": ("par_m2", 15.0, 1)},
        "sdb": {"libelle": "Salle de bains", "prises": ("fixe", 1), "lum": ("fixe", 1)},
        "wc": {"libelle": "WC", "prises": ("fixe", 0), "lum": ("fixe", 1)},
        "couloir": {"libelle": "Couloir / circulation", "prises": ("seuil", 4.0, 1, 0), "lum": ("par_m2", 10.0, 1)},
        "bureau": {"libelle": "Bureau", "prises": ("fixe", 3), "lum": ("fixe", 1)},
        "garage": {"libelle": "Garage / buanderie", "prises": ("fixe", 1), "lum": ("fixe", 1)},
        "veranda": {"libelle": "Extérieur / véranda", "prises": ("fixe", 1), "lum": ("par_m2", 15.0, 1)},
    },
    # Pièce d'implantation des prises spécialisées (première pièce existante de la liste)
    "piece_specialises": {
        "plaque": ["cuisine"], "four": ["cuisine"], "lavevaisselle": ["cuisine"],
        "lavelinge": ["garage", "cuisine"], "chauffeeau": ["sdb"], "pompe": ["garage", "cuisine"],
    },
}

# ---------------------------------------------------------------------------
# Structure — maçonnerie chaînée R+0, semelles filantes (règles simplifiées)
# ---------------------------------------------------------------------------
STRUCTURE = {
    "reference": "Règles simplifiées maçonnerie chaînée (esprit DTU 20.1 / Eurocode 7, ELS)",
    "poids_mur": {"parpaing 20": 2.2, "parpaing 15": 1.8, "brique": 1.6},  # kN/m²
    "surhauteur_mur": 0.3,
    "poids_beton_arme": 25.0,  # kN/m³
    "section_chainage": (0.20, 0.20),
    "charge_toiture": {"legere": 0.5, "tuiles": 0.9},  # kN/m²
    "terrasse_permanente": 6.5,
    "terrasse_exploitation": 1.5,
    "largeur_semelle_min": 0.40,
    "pas_arrondi_semelle": 0.05,
    "hauteur_semelle_min": 0.25,
    "enrobage_hauteur": 0.05,
    "ferraillage_semelle": "3 HA10 filants + HA8 e = 20 cm",
    "poteau": {"section": (0.20, 0.20), "armatures": "4 HA10", "cadres": "HA6 e = 15 cm"},
    "ouverture_poteaux_seuil": 1.8,
    "appui_linteau": 0.20,
    "dallage": {"epaisseur": 0.10, "herisson": 0.15, "treillis": "ST25"},
    "portance_hypothese": 0.15,
    "portance_min_superficielle": 0.08,
    "profondeur_fouille_sup": 0.30,  # sur-profondeur de fouille sous la semelle (hors gel, sol porteur)
}

# ---------------------------------------------------------------------------
# Élévation et modèle 3D (hauteurs conventionnelles, repère : ±0,00 = plancher fini)
# ---------------------------------------------------------------------------
ELEVATION = {
    "reference": "Conventions de dessin d'architecte ; fondations à confirmer par l'étude de sol",
    "terrain_sous_plancher": 0.20,  # le plancher fini est 20 cm au-dessus du terrain naturel
    "assise_sous_terrain": 0.80,  # niveau d'assise de la semelle sous le terrain naturel (hors gel, sol porteur)
    "allege_fenetre": 0.90,
    "allege_haute": 1.60,  # fenêtre de salle d'eau
    "seuil_porte_fenetre": 2.00,  # une ouverture au moins aussi haute est une porte-fenêtre (allège 0)
    "hauteur_chainage": 0.20,
    "hauteur_veranda": 2.60,
    "poteau_veranda": 0.20,
    "entraxe_poteaux_veranda": 3.0,
    "epaisseur_toiture_3d": 0.08,
    "epaisseur_dalle_terrasse": 0.15,
    "hauteur_acrotere": 0.40,
    "terrain_marge_vue": 1.5,  # marge de terrain dessinée de chaque côté de la maison dans l'élévation
}

# ---------------------------------------------------------------------------
# Toiture
# ---------------------------------------------------------------------------
TOITURE = {
    "reference": "Règles professionnelles simplifiées (couverture, charpente bois)",
    "debord": 0.50,
    "pente_min": {"tole bac acier": 10.0, "tole ondulee": 15.0, "tuiles": 40.0, "dalle beton": 1.0},
    "pente_max_terrasse": 2.0,
    "entraxe_fermes": 1.20,
    "entraxe_pannes": {"tole bac acier": 1.0, "tole ondulee": 1.0, "tuiles": 0.6},
    "entraxe_liteaux": 0.33,
    "dalle_terrasse": 0.15,
    "acrotere": 0.40,
    "surface_par_descente": 80.0,
    "descentes_min": 2,
}

# ---------------------------------------------------------------------------
# Secours solaire (prototype validé)
# ---------------------------------------------------------------------------
SOLAIRE = {
    "reference": "Pré-dimensionnement simplifié (prototype Module Électrification)",
    "charges_fixes_w": 600.0,
    "marge_onduleur": 1.25,
    "pas_onduleur_kva": 0.5,
    "facteur_utilisation": 0.6,
    "profondeur_decharge": 0.8,
    "rendement_onduleur": 0.9,
    "facteur_journalier": 0.5,
    "heures_jour": 12.0,
    "ratio_performance": 0.75,
}

# ---------------------------------------------------------------------------
# Métré
# ---------------------------------------------------------------------------
METRE = {
    "reference": "Ratios de métré usuels (indicatifs)",
    "ratio_acier_semelles": 80.0,  # kg/m³
    "ratio_acier_chainages": 120.0,
    "dosage_ciment": 350.0,  # kg/m³
    "sac_ciment": 50.0,
    "sable_par_m3_beton": 0.4,
    "gravier_par_m3_beton": 0.8,
    "blocs_par_m2": 12.5,
    "pertes_blocs": 0.05,
    "mortier_par_m2_mur": 0.02,  # m³ de mortier par m² de maçonnerie
    "pertes_carrelage": 0.10,
    "couches_peinture": 2,
    "foisonnement_terres": 1.0,
}
