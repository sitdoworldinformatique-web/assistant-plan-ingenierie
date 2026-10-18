"""Prix unitaires de départ (USD). INDICATIF — À METTRE À JOUR par l'administrateur.

Ces valeurs servent uniquement à amorcer la table `PrixMateriau` ; elles ne reflètent aucun
marché précis et doivent être remplacées par des prix locaux relevés.
"""
from __future__ import annotations

MENTION = "indicatif — à mettre à jour"

# code : (libellé, unité, prix unitaire USD)
PRIX_DEFAUT: dict[str, tuple[str, str, float]] = {
    "terrassement": ("Terrassement en fouilles", "m³", 8.0),
    "beton_fondation": ("Béton de fondation (semelles)", "m³", 120.0),
    "beton_arme": ("Béton armé chaînages, poteaux, linteaux", "m³", 140.0),
    "acier": ("Acier HA", "kg", 1.6),
    "ciment": ("Ciment (sac de 50 kg)", "sac", 11.0),
    "sable": ("Sable", "m³", 18.0),
    "gravier": ("Gravier", "m³", 28.0),
    "blocs_20": ("Blocs de maçonnerie (murs extérieurs)", "u", 0.9),
    "blocs_10": ("Blocs de 10 (cloisons)", "u", 0.6),
    "mortier": ("Mortier de pose", "m³", 95.0),
    "enduit": ("Enduit ciment 2 faces", "m²", 4.5),
    "dallage": ("Dallage béton 10 cm sur hérisson, treillis ST25", "m²", 16.0),
    "charpente": ("Charpente bois", "ml", 3.5),
    "couverture_tole_bac_acier": ("Couverture tôle bac acier", "m²", 11.0),
    "couverture_tole_ondulee": ("Couverture tôle ondulée", "m²", 7.5),
    "couverture_tuiles": ("Couverture tuiles", "m²", 18.0),
    "dalle_toiture": ("Dalle de toiture béton armé 15 cm", "m³", 160.0),
    "etancheite": ("Étanchéité de toiture terrasse", "m²", 14.0),
    "acrotere": ("Acrotère 40 cm", "ml", 12.0),
    "gouttiere": ("Gouttière", "ml", 6.0),
    "descente": ("Descente d'eaux pluviales", "u", 25.0),
    "porte_entree": ("Porte d'entrée", "u", 280.0),
    "porte_interieure": ("Porte intérieure", "u", 95.0),
    "porte_garage": ("Porte de garage basculante", "u", 450.0),
    "fenetre": ("Fenêtre", "u", 120.0),
    "placard": ("Façade de placard coulissante", "u", 110.0),
    "carrelage": ("Carrelage (pertes comprises)", "m²", 14.0),
    "peinture": ("Peinture 2 couches", "m²", 2.8),
    "cable_1_5": ("Câble cuivre 1,5 mm² (par conducteur)", "m", 0.35),
    "cable_2_5": ("Câble cuivre 2,5 mm² (par conducteur)", "m", 0.55),
    "cable_4": ("Câble cuivre 4 mm² (par conducteur)", "m", 0.85),
    "cable_6": ("Câble cuivre 6 mm² (par conducteur)", "m", 1.25),
    "cable_10": ("Câble cuivre 10 mm² (par conducteur)", "m", 2.1),
    "cable_16": ("Câble cuivre 16 mm² (par conducteur)", "m", 3.3),
    "disjoncteur": ("Disjoncteur divisionnaire", "u", 9.0),
    "interrupteur_diff_ac": ("Interrupteur différentiel 30 mA type AC", "u", 38.0),
    "interrupteur_diff_a": ("Interrupteur différentiel 30 mA type A", "u", 65.0),
    "disjoncteur_branchement": ("Disjoncteur de branchement 500 mA", "u", 85.0),
    "tableau": ("Coffret de tableau électrique", "u", 60.0),
    "prise": ("Prise de courant", "u", 4.5),
    "interrupteur": ("Interrupteur", "u", 3.5),
    "luminaire": ("Point lumineux équipé", "u", 12.0),
    "onduleur": ("Onduleur hybride", "kVA", 220.0),
    "batteries": ("Batteries lithium", "kWh", 320.0),
    "panneaux": ("Panneaux photovoltaïques posés", "kWc", 450.0),
}
