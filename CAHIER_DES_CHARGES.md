# Cahier des charges — ASSISTANT PLAN INGÉNIERIE

> **À l'attention de Claude Code.** Ce document est la spécification complète du produit. Lis-le en entier avant d'écrire du code. Construis le projet **dans l'ordre des lots de la section 12**, en faisant passer les tests de chaque lot avant de passer au suivant. Quand une décision n'est pas couverte ici, choisis l'option la plus simple et la plus sûre, puis note-la dans `docs/DECISIONS.md`.

---

## 1. Le produit en une phrase

Un SaaS web où un constructeur décrit une maison en langage naturel (« villa plain-pied, 3 chambres, terrain 15×20, toiture 2 pans en tôle »). L'IA en tire un programme. Des moteurs de calcul produisent alors le plan, les fondations, la structure, la toiture, l'électrification, le métré et le devis. Un rapport de conformité accompagne le tout, et **un ingénieur relit et signe** avant toute exécution.

**Utilisateurs :**
- **Le constructeur / maître d'œuvre** : saisit le projet, consulte les plans, exporte.
- **L'ingénieur** : vérifie les hypothèses et les résultats, valide module par module, signe.
- **L'administrateur** : gère les comptes, les normes, les prix des matériaux.

**Marché visé :** Afrique francophone (RDC en premier). Il faut donc gérer des connexions lentes, des coupures de courant (le secours solaire est un module de premier rang), le français par défaut et des prix en USD paramétrables.

---

## 2. Principe d'architecture NON NÉGOCIABLE

```
L'IA propose  →  les moteurs déterministes calculent et vérifient  →  l'ingénieur valide et signe
```

1. **Un modèle de langage ne calcule jamais une valeur de sécurité** : section de câble, ferraillage, largeur de semelle, calibre de disjoncteur, chute de tension. Ces valeurs viennent uniquement de fonctions Python pures, testées unitairement, avec des formules explicites.
2. **L'IA sert à :**
   - transformer le texte libre en `Programme` structuré ;
   - proposer des corrections du programme quand un contrôle est bloquant ;
   - expliquer un résultat en langage simple ;
   - générer des images de présentation (Nano Banana).
3. **Les images générées par Nano Banana sont des images de présentation, non contractuelles.** Le plan technique coté (SVG/DXF/PDF) est produit par le code, à partir de la maquette. Chaque image générée porte la mention « Image de présentation — non contractuelle. Cotes et quantités : voir plan technique ».
4. **Maquette unique** : un seul objet `Projet` (programme + résultats). Toute modification du programme relance toute la chaîne de calcul et **annule les validations** de l'ingénieur (une validation est liée à une empreinte SHA-256 des données du projet).
5. **Chaque calcul expose ses hypothèses** (valeurs d'entrée, coefficients, norme de référence) dans un journal visible par l'ingénieur.
6. **Tout document exporté** porte « À valider par un ingénieur qualifié » tant que le module n'est pas signé.

---

## 3. Structure du dépôt (3 parties)

```
assistant-plan-ingenierie/
├── CLAUDE.md                      # résumé de ce cahier des charges + commandes (à créer en premier)
├── CAHIER_DES_CHARGES.md          # ce document
├── docs/DECISIONS.md              # décisions prises pendant le développement
│
├── 1-frontend/                    # PARTIE 1 — interface web
│   ├── package.json  vite.config.ts  index.html
│   ├── src/
│   │   ├── main.tsx  App.tsx  api/client.ts  types.ts
│   │   ├── pages/        Projets.tsx  Projet.tsx  Connexion.tsx
│   │   ├── components/   BarreIA.tsx  PlanViewer.tsx  CalquesPlan.tsx  Electricite.tsx
│   │   │                 Structure.tsx  Toiture.tsx  Metre.tsx  RapportValidation.tsx
│   │   │                 RendusIA.tsx  Signature.tsx  JournalHypotheses.tsx
│   │   ├── lib/          rasteriserSvg.ts  format.ts
│   │   └── styles/       tokens.css  app.css
│   └── Dockerfile
│
├── 2-backend/                     # PARTIE 2 — API et moteurs de calcul
│   ├── app/
│   │   ├── main.py  config.py  schemas.py  stockage.py  auth.py  orchestrateur.py
│   │   ├── moteurs/   programme.py  implantation.py  electricite.py  structure.py
│   │   │              toiture.py  metre.py  solaire.py  regles.py  normes.py
│   │   └── rendu/     plan_svg.py  dxf.py  pdf.py  rapport.py
│   ├── tests/         test_programme.py  test_implantation.py  test_electricite.py
│   │                  test_structure.py  test_toiture.py  test_metre.py
│   │                  test_regles.py  test_api.py  cas_reference/*.json
│   ├── requirements.txt  pyproject.toml
│   └── Dockerfile
│
└── 3-connecteurs-deploiement/     # PARTIE 3 — connecteurs API et mise en production
    ├── connecteurs/apiconnect/   __init__.py  claude.py  nano_banana.py  http.py  erreurs.py
    ├── connecteurs/tests/        test_claude.py  test_nano_banana.py   (avec réponses simulées)
    ├── docker-compose.yml  docker-compose.prod.yml
    ├── nginx/nginx.conf
    ├── .env.example
    ├── scripts/  demarrer-dev.sh  sauvegarde-db.sh
    ├── .github/workflows/ci.yml
    └── DEPLOIEMENT.md
```

Le backend importe les connecteurs via `PYTHONPATH` (`from apiconnect import claude, nano_banana`). Dans Docker, le contexte de build est la racine du dépôt, et le Dockerfile du backend copie `2-backend/` et `3-connecteurs-deploiement/connecteurs/`.

---

## 4. Stack technique

| Couche | Choix | Remarques |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite | Pas de framework CSS lourd ; CSS avec variables (tokens), thème clair et sombre |
| Rendu plan | SVG produit par le backend, affiché dans le navigateur | Zoom/déplacement (pan) côté client, calques activables par classes CSS |
| Backend | Python 3.12, FastAPI, Pydantic v2, Uvicorn | Moteurs = fonctions pures sans dépendance web |
| Base de données | PostgreSQL 16 (SQLite en développement) | SQLAlchemy 2 + Alembic pour les migrations |
| Export DXF | `ezdxf` | Calques : MURS, PORTES, FENETRES, COTES, TEXTES, ELEC, STRUCTURE |
| Export PDF | `weasyprint` ou `reportlab` | Plan + cartouche + notes de calcul |
| SVG → PNG | rasterisation dans le navigateur (canvas), envoyée au backend | Évite une dépendance système côté serveur ; `cairosvg` en option |
| IA texte | API Claude (SDK `anthropic`) | Modèle configurable par variable d'env, défaut `claude-sonnet-5-5` |
| IA image | API Gemini — Nano Banana | Modèle configurable, défaut `gemini-nano-banana-2.1` |
| Auth | JWT (email + mot de passe), rôles `constructeur`, `ingenieur`, `admin` | Mots de passe hachés avec argon2 ou bcrypt |
| Déploiement | Docker Compose + Nginx (TLS via Let's Encrypt) | VPS simple ; voir section 11 |
| Tests | pytest (backend, connecteurs), Vitest (frontend), Playwright (1 parcours e2e) | |

---

## 5. Modèle de données

### 5.1 `Programme` (entrée de tous les moteurs)

| Champ | Type | Défaut | Notes |
|---|---|---|---|
| nom | str | « Maison individuelle » | |
| niveaux | int | 1 | MVP : 1 seul (R+0). `>1` → contrôle **bloquant** « non pris en charge » |
| chambres | int 0–8 | 3 | |
| salles_de_bain | int 1–4 | 1 | |
| wc_separe | bool | true | |
| bureau, garage, veranda | bool | false, false, true | |
| cuisine_ouverte | bool | false | |
| surface_sejour | float m² | 0 = auto | |
| terrain_largeur, terrain_profondeur | float m | 15, 20 | |
| recul | float m | 2.0 | distance minimale aux limites |
| hauteur_sous_plafond | float m | 3.0 | |
| toiture | enum | « 2 pans » | « 2 pans », « 4 pans », « terrasse » |
| couverture | enum | « tole bac acier » | « tole bac acier », « tole ondulee », « tuiles », « dalle beton » |
| pente_toiture | float % | 25 | |
| maconnerie | enum | « parpaing 20 » | « parpaing 20 », « parpaing 15 », « brique » |
| portance_sol | float MPa | 0.15 | **hypothèse prudente** tant que `portance_mesuree` = false |
| portance_mesuree | bool | false | |
| clim_chambres, clim_sejour | bool | true | |
| equipements | list | plaque, four, lavelinge, chauffeeau, pompe | valeurs possibles : + lavevaisselle |
| resistance_terre | float Ω \| null | null | mesurée sur site |
| solaire | bool | true | |
| autonomie_h, ensoleillement_h | float | 6, 4.5 | |
| devise | str | « USD » | |
| longueurs_circuits | dict clé→m | {} | surcharges saisies par l'utilisateur |

### 5.2 `Projet` (stocké en base, JSON)

```
Projet {
  id, proprietaire_id, nom, cree_le, modifie_le,
  texte_initial: str,
  programme: Programme,
  resultats: {
    implantation: { emprise, pieces[], murs[], ouvertures[], cotes[] },
    electricite:  { circuits[], differentiels[], bilan, points[] },
    structure:    { semelles[], poteaux[], chainages[], hypotheses[] },
    toiture:      { surface, pente, fermes, pannes, gouttieres, hypotheses[] },
    solaire:      { charges_essentielles_w, onduleur_kva, batteries_kwh, panneaux_kwc },
    metre:        { lignes[ {poste, quantite, unite, prix_unitaire, total} ], total },
    controles:    [ { id, module, niveau: "ok"|"avertissement"|"bloquant", titre, detail, reference_norme } ],
    hypotheses:   [ { module, libelle, valeur, source } ]
  },
  empreinte: sha256(programme + version des moteurs),
  journal_ia: [ { date, etape, entree_resume, sortie_resume, modele } ],
  version_moteurs: str
}
Validation { id, projet_id, module, ingenieur_id, nom, numero_ordre, empreinte, date, commentaire }
Rendu      { id, projet_id, style, chemin_fichier, prompt, modele, date }
Utilisateur{ id, email, mot_de_passe_hache, nom, role, numero_ordre? }
PrixMateriau { code, libelle, unite, prix, devise, mis_a_jour_le }   # éditable par l'admin
```

Les tables `Validation`, `Rendu` et `Utilisateur` sont relationnelles ; `programme` et `resultats` sont des colonnes JSONB.

---

## 6. Les moteurs de calcul (PARTIE 2)

Règles communes :
- Chaque moteur est une **fonction pure** `calculer(programme, ...) -> Resultat` sans accès réseau ni base.
- Chaque moteur renvoie ses `controles` et ses `hypotheses`.
- Unités : mètres, m², kN, MPa, W, A, V. Les arrondis ne se font qu'à l'affichage.
- Toutes les constantes vivent dans `normes.py`, groupées par référentiel, pour pouvoir ajouter plus tard des normes locales sans toucher aux moteurs.

### 6.1 Implantation (plan 2D) — `implantation.py`

Génère une maison rectangulaire en **trois bandes** (y vers le bas, façade principale en bas) :

```
┌───────────────── bande nuit (profondeur Dn = 3,6 m) ─────────────────┐
│ Chambre parentale │ Chambre 2 │ Chambre 3 │ Bloc sanitaire (SdB+WC)  │
├──────────────────────── couloir (1,2 m) ─────────────────────────────┤
│        Séjour            │  (Bureau)  │        Cuisine               │
└───────────────── bande jour (profondeur Dj calculée) ────────────────┘
                 [ Véranda devant le séjour, hors murs ]
 Garage optionnel accolé à gauche de la bande jour
```

**Surfaces cibles (m²) :**
- séjour : `max(20 + 4 × chambres, surface_sejour)` ;
- cuisine : 11 ;
- chambre parentale : 14 ; autres chambres : 11,5 ;
- salle de bains : ≈ 6,8 (1,9 × Dn) ;
- WC : 1,1 × 1,8 ;
- bureau : 9 ;
- garage : 3,2 × Dj.

**Algorithme :**
1. Largeurs de la bande nuit : chambre = surface / Dn ; bloc sanitaire = 3,0 m (SdB 1,9 m sur toute la profondeur + WC 1,1 × 1,8 côté couloir + placard 1,1 × 1,8 ouvert sur la chambre voisine). Chaque salle de bain supplémentaire ajoute une tranche de 1,9 m.
2. W = somme des largeurs de la bande nuit.
3. Dj = (séjour + cuisine + bureau) / W, borné à [4,2 ; 6,5] m. Cuisine et bureau : largeur = surface / Dj. Le séjour prend le reste de W.
4. Contrôle d'emprise : W (+ garage) + 2 × recul ≤ terrain_largeur et D + véranda + 2 × recul ≤ terrain_profondeur. Sinon **bloquant**, et l'orchestrateur demande une correction à l'IA.
5. Murs : extérieurs 0,20 m (0,15 si parpaing 15), cloisons 0,10 m.
6. Ouvertures :
   - porte d'entrée 0,90 m en façade du séjour ;
   - portes intérieures 0,80 m (0,70 m pour le WC) sur le côté couloir ;
   - séjour ouvert sur le couloir par une baie de 1,40 m ;
   - fenêtres : chambres 1,20 m, séjour 2 × 1,60 m, cuisine 1,20 m, SdB 0,60 m (allège haute), bureau 1,20 m.
7. Surfaces **nettes** = dimensions entre nus intérieurs des murs. Elles sont affichées sur le plan et utilisées par les autres moteurs.

**Contrôles :**
- surface nette minimale : chambre ≥ 9 m², séjour ≥ 18 m² ;
- largeur de couloir ≥ 0,90 m ;
- chaque pièce habitable a au moins une fenêtre (éclairement des baies ≥ 1/6 de la surface : avertissement sinon) ;
- chaque pièce a une porte.

### 6.2 Rendu du plan technique — `rendu/plan_svg.py` (c'est ici que se joue la qualité)

Le plan doit ressembler à un **plan d'architecte professionnel à l'échelle 1:100** :
- **Technique de dessin** : remplir l'emprise avec la couleur des murs, puis « creuser » chaque pièce (rectangle réduit de la demi-épaisseur des murs) avec la couleur du sol. Les murs apparaissent ainsi automatiquement, avec des jonctions propres. Les murs extérieurs sont hachurés à 45°.
- **Portes** : ouverture dans le mur, vantail en trait fin et arc de débattement de 90°.
- **Fenêtres** : trois traits parallèles dans l'épaisseur du mur.
- **Étiquettes** : nom de la pièce, surface nette « 12,40 m² », dimensions « 3,30 × 3,40 ».
- **Cotation** : chaîne extérieure (cotes totales et cotes de chaque pièce) en bas et à gauche, flèches obliques, texte au-dessus de la ligne.
- **Annotations** : flèche du nord, échelle graphique 0–5 m, cartouche (projet, plan RDC, échelle, date, version, statut « À valider par un ingénieur » ou nom de l'ingénieur signataire).
- **Calques** = groupes `<g>` avec classes : `calque-murs`, `calque-cotes`, `calque-mobilier` (optionnel), `calque-elec` (symboles NF : point lumineux ⊗, prise, interrupteur, tableau, prises spécialisées), `calque-structure` (semelles en pointillé, poteaux pleins).
- **Couleurs via variables CSS** : le même SVG doit être lisible en thème clair et sombre.
- **Polices** : une police technique condensée (IBM Plex Sans Condensed) pour les étiquettes, une monospace pour les cotes.
- **Tests** : SVG valide (parse XML), aucun texte hors du `viewBox`, nombre de portes = nombre de pièces, et un test « golden » avec un snapshot SVG pour le cas de référence.

### 6.3 Électrification — `electricite.py`

Reprendre **exactement** la logique du prototype déjà validé (artifact « Module Électrification ») :

| Règle | Valeur |
|---|---|
| Tension | 230 V monophasé, cos φ 0,9 |
| Résistivité cuivre en service | ρ = 0,023 Ω·mm²/m |
| Chute de tension | ΔU % = 2 × ρ × L × Ib / (S × U) × 100 ; limite 3 % éclairage, 5 % autres |
| Éclairage | 1,5 mm², disjoncteur 16 A, 8 points max par circuit, 100 W par point (hypothèse) |
| Prises | 2,5 mm², disjoncteur 20 A, 12 prises max, Ib = 16 A (0,8 × In), 300 W/prise, ks 0,25 |
| Prises cuisine | circuit dédié, 6 prises (dont 4 au plan de travail) si cuisine > 4 m², ks 0,3 |
| Prises par pièce | séjour 1 / 4 m² (min 5) ; chambre 3 ; SdB 1 ; couloir > 4 m² : 1 ; bureau 3 ; garage/extérieur 1 |
| Points lumineux | séjour 1 / 20 m² ; cuisine 1 / 15 m² ; couloir 1 / 10 m² ; autres 1 |
| Spécialisés | plaque 7 200 W 32 A 6 mm² ks 0,7 (type A) ; four 3 000 W 20 A 2,5 ks 0,75 ; lave-linge 2 500 W 20 A 2,5 ks 0,75 (type A) ; lave-vaisselle 2 000 W 20 A ks 0,75 ; chauffe-eau 2 000 W 20 A ks 1 ; pompe 1 100 W 16 A ks 1 ; climatiseur 1 200 W 20 A 2,5 ks 0,8 (un circuit par appareil) |
| Iz (méthode B, PVC, 2 conducteurs) | 1,5 → 17,5 A ; 2,5 → 24 ; 4 → 32 ; 6 → 41 ; 10 → 57 ; 16 → 76 |
| Vérification | Ib ≤ In ≤ Iz sinon **bloquant** |
| Si ΔU dépasse la limite | section supérieure automatique (avertissement « section augmentée ») ; si 16 mm² ne suffit pas → **bloquant** |
| Différentiels 30 mA | ≤ 8 circuits par ID ; nombre selon surface (< 35 m² : 1, ≤ 100 m² : 2, > 100 m² : 3) ; plaque et lave-linge sous un ID **type A** ; répartition circulaire des autres circuits pour séparer les éclairages ; calibre 40 A, ou 63 A si Σ(Ib × ks) > 40 A |
| Bilan | P appelée = Σ(P × ks) × foisonnement général 0,6 ; kVA = P / 0,9 ; calibre de branchement ∈ {15, 30, 45, 60} A ; au-delà de 60 A → avertissement « étudier le triphasé 400 V » |
| Terre | null → **bloquant** « mesure requise » ; ≤ 100 Ω ok ; ≤ 500 Ω avertissement ; > 500 Ω **bloquant** |
| Avertissements permanents | volumes de la SdB ; IP44 en extérieur ; parafoudre recommandé |

**Nouveau par rapport au prototype :**
- **Placement des symboles** sur le plan : un point lumineux au centre de la pièce ; les prises réparties le long des murs (pas dans l'arc des portes, ≥ 0,30 m des angles) ; un interrupteur côté poignée de la porte ; le tableau près de l'entrée.
- **Longueur de chaque circuit** = distance de Manhattan entre le tableau et le point le plus éloigné du circuit, + 2 m de remontées, + 10 %. L'utilisateur peut la surcharger.
- **Schéma unifilaire** en SVG (arrivée, disjoncteur de branchement 500 mA, rangées par ID, disjoncteurs divisionnaires, libellés).

### 6.4 Structure et fondations — `structure.py`

Périmètre MVP : maison R+0 en maçonnerie chaînée, fondations par semelles filantes.

- **Descente de charges par mètre linéaire de mur porteur (ELS) :**
  - mur : poids surfacique (parpaing 20 : 2,2 kN/m² ; parpaing 15 : 1,8 ; brique : 1,6) × hauteur (HSP + 0,3) ;
  - chaînages : 25 kN/m³ × 0,20 × 0,20 ;
  - toiture légère (tôle + charpente) : 0,5 kN/m² ; tuiles : 0,9 ; terrasse béton : 6,5 (dalle 0,15 + étanchéité) + exploitation 1,5 ; le tout × largeur reprise (demi-portée).
- **Semelle filante** : B = q_ELS / σ_sol, minimum 0,40 m, arrondie aux 5 cm supérieurs. Hauteur h = max(0,25 ; (B − e_mur)/4 + 0,05). Ferraillage forfaitaire minimal 3 HA10 filants + HA8 e = 20 cm, marqué « minimum constructif — à justifier par l'ingénieur ».
- **Poteaux / chaînages verticaux** 20 × 20 (4 HA10, cadres HA6 e = 15) à chaque angle, à chaque jonction de murs et de part et d'autre des ouvertures > 1,8 m.
- **Chaînage horizontal haut** 20 × 20 sur tous les murs ; linteaux au-dessus de chaque ouverture (portée + 2 × 0,20).
- **Dallage** : béton 0,10 m sur hérisson 0,15 m, treillis soudé ST25.
- **Contrôles :**
  - `portance_mesuree = false` → **avertissement** « portance supposée 0,15 MPa, étude géotechnique recommandée » ;
  - σ_sol < 0,08 MPa → **bloquant** « fondations superficielles inadaptées, étude spécifique » ;
  - niveaux > 1 → **bloquant**.

### 6.5 Toiture — `toiture.py`

- Débord de 0,50 m. Surface rampante = surface en plan avec débords / cos(arctan(pente)).
- Pentes minimales : tôle bac acier 10 % ; tôle ondulée 15 % ; tuiles 40 % ; terrasse 1–2 %. En dessous → **bloquant**.
- **Charpente bois (2 pans)** : fermes tous les 1,20 m, pannes tous les 1,0 m (tôle) ou 0,6 m (tuiles), liteaux pour tuiles.
- **4 pans** : arêtiers en plus.
- **Terrasse** : dalle 0,15 m, acrotère 0,40 m.
- **Eaux pluviales** : gouttières = longueur des égouts. Descentes : 1 pour 80 m² de toiture projetée, minimum 2.
- **Contrôle « zone cyclonique / vents forts »** : avertissement demandant l'ancrage des fermes dans le chaînage.

### 6.6 Secours solaire — `solaire.py`

Reprendre le prototype :
- P essentielle = éclairage + 600 W + pompe éventuelle ;
- onduleur = arrondi supérieur au 0,5 kVA de (P × 1,25) ;
- batteries kWh = P × 0,6 × autonomie / (0,8 × 0,9) ;
- énergie journalière = P × 0,5 × 12 h ;
- panneaux kWc = E_jour / (ensoleillement × 0,75).

Toutes ces valeurs sont des hypothèses affichées.

### 6.7 Métré et devis — `metre.py`

Postes minimum, chacun avec quantité, unité, prix unitaire (table `PrixMateriau`) et total :
- terrassement (m³) ;
- béton de fondation (m³) ;
- acier (kg, ratio 80 kg/m³ en semelles, 120 kg/m³ en chaînages) ;
- ciment (sacs de 50 kg à 350 kg/m³) ;
- sable et gravier (m³) ;
- maçonnerie : nombre de blocs = surface nette des murs (déduction des ouvertures) × 12,5 + 5 % de pertes ;
- mortier ;
- enduit 2 faces (m²) ;
- dallage (m²) ;
- charpente (ml) et couverture (m²) ;
- gouttières (ml) ;
- menuiseries (unités) ;
- carrelage (m² + 10 %) ;
- peinture (m², 2 couches) ;
- câbles par section (m, × 3 conducteurs) ;
- disjoncteurs, ID, tableau, prises, interrupteurs, luminaires (unités) ;
- kit solaire.

Les prix fournis au départ sont des **exemples marqués « indicatif — à mettre à jour »**. L'admin les modifie dans l'interface. Export CSV et XLSX.

### 6.8 Règles et statut global — `regles.py`

- Agrège les contrôles de tous les modules.
- Statut du projet : `bloque` s'il existe au moins un contrôle **bloquant**, sinon `conforme_avec_reserves` s'il existe des avertissements, sinon `conforme`.
- Statut de chaque module : même logique, limitée à ses contrôles.
- Chaque contrôle a un identifiant stable (ex. `ELEC-DU-C4`) pour l'historique et les commentaires.

---

## 7. Le système d'automatisation par l'IA — `orchestrateur.py`

Le pipeline complet est déclenché par `POST /api/projets/generer` :

```
1. INTERPRÉTER   texte → Programme      (Claude, sortie structurée par tool use ; secours : analyseur par règles)
2. CALCULER      Programme → implantation → électricité → structure → toiture → solaire → métré
3. CONTRÔLER     regles.py → liste de contrôles + statut
4. AUTO-CORRIGER s'il y a des bloquants « corrigeables » (emprise, pente, surfaces) :
                 envoyer à Claude {programme, contrôles bloquants} → il renvoie un Programme corrigé
                 + une explication ; recalculer ; au maximum 2 itérations ; ne JAMAIS modifier
                 resistance_terre, portance_sol ou portance_mesuree (données de terrain)
5. DESSINER      plan SVG technique + schéma unifilaire
6. JOURNALISER   chaque étape IA dans journal_ia (modèle, résumé entrée/sortie, durée)
7. RENDRE        (à la demande, pas automatiquement) images Nano Banana
```

**Exigences :**
- **Claude en sortie structurée** : définir un outil `definir_programme` dont l'`input_schema` est le JSON Schema de `Programme` (généré par Pydantic), et forcer `tool_choice: {"type": "tool", "name": "definir_programme"}`. Valider la sortie avec Pydantic ; en cas d'échec, une nouvelle tentative, puis le secours par règles.
- **Prompt système de l'interprétation** : rôle d'architecte-programmiste ; ne jamais inventer de données de terrain ; laisser les valeurs par défaut quand le texte ne dit rien ; signaler dans un champ `remarques` ce qui est ambigu.
- **Auto-correction** : outil `corriger_programme` qui renvoie `{programme, explication, champs_modifies[]}`. Le backend vérifie que seuls des champs autorisés ont changé.
- **Expliquer** : `POST /api/projets/{id}/expliquer {element_id}`. Claude reçoit le contrôle ou le circuit concerné et ses hypothèses, et répond en français simple, en 120 mots maximum. Il n'a pas le droit de changer une valeur.
- **Sans clé API**, l'application fonctionne entièrement : analyseur par règles, pas d'auto-correction (les bloquants sont simplement affichés), rendus IA désactivés avec un message clair.

---

## 8. Rendus de présentation Nano Banana (qualité visuelle)

But : des images de présentation de grande qualité pour le client final, **à partir du plan exact**.

**Styles proposés :**
1. **« Plan coloré meublé »** : vue de dessus, sols texturés, mobilier, ombres douces.
2. **« Vue 3D isométrique coupée »** : maison sans toit, vue à 45°.
3. **« Façade principale »** : rendu photoréaliste de la façade.
4. **« Perspective extérieure »** : vue d'ensemble avec la véranda.

**Flux :**
1. Le frontend rasterise le SVG technique (calques murs + ouvertures uniquement, sans cotes) en PNG 2048 px via un `canvas`.
2. Il envoie `POST /api/projets/{id}/rendus { style, image_base64 }`.
3. Le backend construit le prompt et appelle le connecteur.
4. L'image reçue est enregistrée (stockage disque ou S3), avec la mention « non contractuelle » ajoutée en bas de l'image (Pillow), puis renvoyée à l'interface.

**Prompt** (gabarit dans `apiconnect/nano_banana.py`) : il donne la liste des pièces avec leurs dimensions et des consignes strictes :
- conserver exactement la position et la forme des murs, des portes et des fenêtres de l'image fournie ;
- ne pas ajouter ni supprimer de pièce ;
- pas de texte inventé ;
- style architectural professionnel, lumière naturelle, matériaux adaptés au climat tropical (enduits clairs, tôle, carrelage).

**API Gemini à utiliser** (vérifiée en octobre 2026 sur la [documentation officielle Nano Banana](https://ai.google.dev/gemini-api/docs/nanobanana) — **relire cette page au moment de coder**, les identifiants de modèles changent souvent) :
- `POST https://generativelanguage.googleapis.com/v1beta/interactions`, en-tête `x-goog-api-key: $GEMINI_API_KEY` ;
- corps : `{"model": "gemini-nano-banana-2.1", "input": [{"type":"text","text": PROMPT}, {"type":"image","mime_type":"image/png","data": BASE64}], "response_format": {"type":"image","mime_type":"image/jpeg","aspect_ratio":"16:9","image_size":"2K"}}` ;
- l'image revient en base64 (`output_image.data` dans le SDK Python `google-genai`). Écrire un analyseur de réponse tolérant, qui cherche aussi dans `steps[].content[]` les blocs `type: "image"` ;
- modèles possibles : `gemini-nano-banana-2.1` (défaut recommandé), `gemini-3-pro-image` (qualité premium), `gemini-3.1-flash-lite-image` (économique) ;
- variables d'env : `GEMINI_API_KEY`, `NANO_BANANA_MODEL`.

**Garde-fous** : quota de rendus par utilisateur et par jour (`RENDUS_MAX_PAR_JOUR`, défaut 10) ; délai d'attente de 90 s ; erreurs claires (« Le service d'images n'a pas répondu, réessayez dans une minute »).

---

## 9. API REST (PARTIE 2)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/sante` | état, version des moteurs, IA texte/image configurées oui/non |
| POST | `/api/auth/inscription`, `/api/auth/connexion` | JWT |
| POST | `/api/ia/interpreter` | `{texte}` → `{programme, remarques}` (sans enregistrer) |
| POST | `/api/projets/generer` | `{texte?, programme?}` → Projet complet (pipeline section 7) |
| GET | `/api/projets` · `/api/projets/{id}` | liste · détail |
| PUT | `/api/projets/{id}/programme` | modifie le programme → recalcul complet → validations annulées |
| DELETE | `/api/projets/{id}` | suppression |
| GET | `/api/projets/{id}/plan.svg?calques=murs,cotes,elec` | plan technique |
| GET | `/api/projets/{id}/unifilaire.svg` | schéma électrique |
| GET | `/api/projets/{id}/plan.dxf` · `/dossier.pdf` · `/metre.xlsx` · `/rapport.txt` | exports |
| POST | `/api/projets/{id}/expliquer` | `{element_id}` → texte |
| POST | `/api/projets/{id}/rendus` · GET `/api/projets/{id}/rendus` | images Nano Banana |
| POST | `/api/projets/{id}/validations` | `{module, commentaire}` — rôle `ingenieur` ; refus 409 si le module a un bloquant |
| GET | `/api/projets/{id}/validations` | liste, avec indicateur « encore valide » (empreinte identique) |
| GET/PUT | `/api/admin/prix` | table des prix (rôle `admin`) |

Erreurs : JSON `{code, message}` en français, codes HTTP corrects. Documentation OpenAPI automatique sur `/api/docs`.

---

## 10. Interface (PARTIE 1)

### 10.1 Écrans

1. **Connexion / inscription.**
2. **Mes projets** : cartes avec nom, date, statut (pastille), miniature du plan, bouton « Nouveau projet ».
3. **Projet** : en-tête (nom, statut global, boutons d'export) et **barre IA** en haut (« Décrivez la maison… » + bouton « Générer »). Une zone de progression affiche les étapes du pipeline. Le contenu est réparti en onglets :
   - **Plan** : visionneuse SVG (zoom molette/pincement, pan, bouton « ajuster »), cases à cocher des calques, clic sur une pièce → panneau latéral avec ses données ;
   - **Programme** : formulaire de toutes les données de `Programme`, avec un bouton « Recalculer » ;
   - **Électricité** : tableau des circuits groupés par ID (longueurs modifiables), schéma unifilaire, bilan ;
   - **Structure** : semelles, poteaux, chaînages, avec hypothèses ;
   - **Toiture** ;
   - **Solaire** ;
   - **Métré & devis** : tableau, total, export ;
   - **Validation** : rapport à 3 niveaux filtrable, bouton « Expliquer » sur chaque ligne, journal des hypothèses, journal IA, signature par module (rôle ingénieur) ;
   - **Rendus IA** : choix du style, bouton « Générer l'image », galerie avec la mention « non contractuelle ».
4. **Admin** : prix des matériaux, utilisateurs.

### 10.2 Exigences d'interface

- Le français partout ; formats français (virgule décimale, « 12,40 m² »).
- **Responsive** : utilisable sur téléphone (le plan en plein écran, les onglets en liste déroulante).
- **Connexion lente** : bundle initial < 300 Ko gzip, chargement paresseux des onglets, état « en cours » visible, reprise sur erreur réseau.
- Thème clair et sombre par variables CSS. Identité visuelle « bureau d'études » : bleu technique, gris légèrement bleutés, IBM Plex Sans / Plex Sans Condensed / Plex Mono. Pastilles d'état vert / orange / rouge, toujours accompagnées d'un texte.
- Accessibilité : focus visible, contrastes AA, libellés sur tous les champs.
- Le bouton d'export « Bon pour exécution » est désactivé tant qu'un module n'est pas signé.

---

## 11. Connecteurs et déploiement (PARTIE 3)

### 11.1 Connecteurs (`apiconnect`)

- `http.py` : client HTTP commun (httpx) avec délais, 2 nouvelles tentatives avec back-off sur 429/5xx, journalisation sans jamais écrire les clés.
- `claude.py` : `interpreter(texte) -> dict`, `corriger(programme, controles) -> dict`, `expliquer(contexte) -> str`. Utiliser le SDK `anthropic`. Variables : `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` (défaut `claude-sonnet-5-5`).
- `nano_banana.py` : `generer_rendu(image_png: bytes, style: str, pieces: list) -> bytes` (section 8).
- `erreurs.py` : `IANonConfiguree`, `IAIndisponible`, `ReponseInvalide`.
- Les tests simulent les réponses HTTP : aucun appel réel en CI.

### 11.2 Déploiement

- **`docker-compose.yml`** (développement) : `db` (postgres:16), `backend` (uvicorn --reload), `frontend` (vite dev).
- **`docker-compose.prod.yml`** : `db` avec volume persistant ; `backend` (gunicorn + uvicorn workers) ; `frontend` construit puis servi par `nginx` ; `nginx` en reverse proxy (`/api` → backend, le reste → fichiers statiques), gzip, cache des fichiers statiques ; `certbot` pour le TLS.
- **`.env.example`** : `DATABASE_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `GEMINI_API_KEY`, `NANO_BANANA_MODEL`, `RENDUS_MAX_PAR_JOUR`, `CORS_ORIGINS`, `STOCKAGE_RENDUS` (chemin ou S3).
- **CI GitHub Actions** : lint (ruff, eslint), tests backend et connecteurs, build frontend, build des images Docker.
- **`DEPLOIEMENT.md`** pas à pas pour un VPS Ubuntu (installer Docker, cloner, remplir `.env`, `docker compose -f docker-compose.prod.yml up -d`, nom de domaine, TLS, sauvegarde quotidienne de la base via `scripts/sauvegarde-db.sh` et cron), plus une variante Render/Railway.
- Les secrets ne sont jamais dans le dépôt ; `.env` est dans `.gitignore`.

---

## 12. Lots de développement (ordre imposé à Claude Code)

| Lot | Contenu | Critère de fin |
|---|---|---|
| **0** | Squelette du dépôt, `CLAUDE.md`, Docker Compose de dev, `/api/sante` | `docker compose up` affiche la page d'accueil et l'API répond |
| **1** | `programme.py` (modèle + analyseur par règles) + tests | 15 phrases de test correctement interprétées |
| **2** | `implantation.py` + `plan_svg.py` + tests golden | Plan du cas de référence lisible, coté, sans chevauchement ; revue visuelle de la capture PNG |
| **3** | `electricite.py` (port du prototype) + placement des symboles + unifilaire | Le cas de référence donne exactement les mêmes circuits que le prototype |
| **4** | `structure.py`, `toiture.py`, `solaire.py`, `metre.py`, `regles.py` | Tests de chaque formule avec valeurs calculées à la main dans les tests |
| **5** | API FastAPI + stockage + auth + validations à empreinte | `test_api.py` couvre le parcours générer → modifier → valider → modifier (validation annulée) |
| **6** | Connecteurs Claude (interpréter, corriger, expliquer) + orchestrateur | Pipeline complet avec réponses simulées ; secours sans clé |
| **7** | Frontend : projets, barre IA, onglets Plan / Programme / Électricité / Validation | Parcours e2e Playwright : texte → plan affiché → export SVG |
| **8** | Frontend : Structure, Toiture, Solaire, Métré, Admin prix | |
| **9** | Nano Banana (connecteur + rasterisation + galerie + quotas) | Rendu obtenu sur le cas de référence avec une vraie clé (test manuel documenté) |
| **10** | Exports DXF, PDF, XLSX | DXF ouvert sans erreur dans un lecteur DXF ; PDF avec cartouche |
| **11** | Déploiement prod, CI, `DEPLOIEMENT.md` | Déploiement réussi sur un VPS de test en suivant le guide à la lettre |

**Cas de référence** (`tests/cas_reference/villa_3ch.json`) : « Villa plain-pied, 3 chambres, 1 salle de bain, WC séparé, cuisine fermée, véranda, terrain 15×20, toiture 2 pans en tôle bac acier, parpaing 20, clim dans les chambres et le séjour, plaque, four, lave-linge, chauffe-eau, pompe, résistance de terre 45 Ω. »

---

## 13. Ce que Claude Code ne doit PAS faire

- Faire calculer par un LLM une section, une charge, un calibre ou une quantité.
- Présenter une image Nano Banana comme un plan technique ou en extraire des cotes.
- Laisser l'IA modifier des données de terrain (terre, portance du sol).
- Marquer un module « validé » sans action explicite d'un utilisateur ayant le rôle `ingenieur`.
- Coder une norme en dur dans un moteur (tout passe par `normes.py`).
- Écrire une clé API dans le code, les logs ou le dépôt.
- Ajouter une fonctionnalité hors de ce document sans la noter dans `docs/DECISIONS.md`.

---

## 14. Hors périmètre du MVP (versions suivantes)

R+1 et plus (dalles, escaliers, poteaux-poutres calculés selon l'Eurocode 2) ; plomberie et assainissement (fosse septique) ; export IFC/BIM ; vue 3D interactive (Three.js) ; édition graphique libre des murs ; normes locales spécifiques ; mode hors ligne complet ; application mobile ; paiement par packs ou abonnement (Mobile Money).
