# Décisions de développement

Chaque choix non couvert par le cahier des charges est noté ici (option la plus simple et la plus sûre).

## Avancement des lots
| Lot | État |
|---|---|
| 0 | fait — `docker compose up` sert la page (5173) et `/api/sante` (8000) |
| 1 | fait — 15 phrases de test interprétées par l'analyseur par règles |
| 2 | fait — plan coté du cas de référence, golden SVG, captures dans `docs/captures/` |
| 3 | fait — mêmes circuits que le prototype, vérifié en exécutant son JavaScript (4 variantes) |
| 4 | fait — structure, toiture, solaire, métré, règles ; formules vérifiées par des valeurs calculées à la main |
| 5 | fait — API, stockage, auth JWT, validations liées à l'empreinte ; parcours générer → modifier → valider → modifier testé |
| 6 | fait — connecteurs Claude et Nano Banana testés avec réponses simulées ; pipeline complet (interprétation, auto-correction, refus des champs interdits, secours sans clé) ; `/expliquer` |
| 7 | fait — écrans connexion, projets, projet (barre IA, onglets Plan, Programme, Électricité, Validation) ; e2e Playwright texte → plan → export SVG, sur bureau et téléphone ; captures `docs/captures/lot7-*` |

## Décisions

### D-001 — Certificat d'autorité optionnel dans les Dockerfiles
Les `RUN pip install` / `npm ci` acceptent un secret BuildKit facultatif `ca`
(`docker build --secret id=ca,src=ca.crt`) pour fonctionner derrière un proxy TLS d'entreprise.
Sans secret, le comportement est standard.

### D-002 — Frontend de dev dans une image Node officielle
En développement, le service `frontend` utilise `node:22-alpine` avec le code monté en volume
(`npm install && vite`), au lieu d'une image dédiée. Le `Dockerfile` du frontend sert la production
(build puis Nginx).

### D-003 — Variables de configuration sans dépendance supplémentaire
`app/config.py` lit `os.environ` dans une dataclass figée (pas de `pydantic-settings`).
`JWT_DUREE_H` (défaut 24) ajouté pour la durée de validité des jetons.

### D-004 — Analyseur par règles : données de terrain
La portance n'est marquée « mesurée » que si le texte parle de mesure, d'étude ou d'essai.
La résistance de terre n'est jamais supposée : son absence produit une remarque.
Si le texte cite des équipements, la liste devient exactement ceux cités ; « sans X » retire X des valeurs par défaut.

### D-005 — Implantation : géométrie à l'axe des murs
Les largeurs calculées (surface / profondeur) sont des dimensions à l'axe des murs. Les surfaces
nettes en sont déduites par la demi-épaisseur de chaque mur adjacent. L'emprise se mesure aux nus extérieurs.

### D-006 — Cas de référence bloquant en largeur
Avec les surfaces du § 6.1, la villa de référence mesure 13,48 m hors tout ; avec 2 × 2 m de recul,
il faut 17,48 m alors que le terrain fait 15 m. Le contrôle `IMPL-EMPRISE-L` est donc **bloquant**
sur le cas de référence, comme le prévoit la règle (auto-correction par l'IA, ou affichage du bloquant sans clé).

### D-007 — Implantation : cas non décrits
- Colonne WC/placard (1,10 m) placée entre la dernière chambre et la salle de bains : placard en haut
  (ouvert sur la chambre voisine), WC en bas (côté couloir). Sans WC séparé, le bas devient un rangement.
  Sans chambre, le placard ouvre sur la salle de bains.
- Si le séjour fait moins de 3,60 m de large, la maison est élargie et le surplus va à la chambre parentale.
- Cuisine ouverte : baie de 2,00 m sur le séjour au lieu d'une porte ; avec un bureau, l'ordre devient
  Séjour | Cuisine | Bureau pour que la cuisine touche le séjour.
- Garage : porte basculante 2,40 m en façade ; le mur garage/séjour est un refend porteur de l'épaisseur extérieure.
- Toiture terrasse : les deux murs du couloir deviennent des refends porteurs (épaisseur extérieure).
- Hauteurs de fenêtres (hypothèses, `normes.py`) : chambres et bureau 1,35 m, séjour 2,15 m (porte-fenêtre),
  cuisine 1,15 m, SdB 0,60 m. Avec la règle du 1/6, la plupart des pièces sortent en avertissement.
- Véranda : 2,50 m de profondeur, largeur du séjour, hors murs. Nord supposé vers le haut du plan.
- Placard et rangement ne sont pas des pièces à desservir par une porte (ouverture de type `placard`).

### D-008 — Plan SVG
1 unité SVG = 1 cm réel ; `width`/`height` en mm donnent l'échelle 1:100 à l'impression. Calques :
`murs`, `textes`, `cotes`, `mobilier` (vide pour l'instant), `elec`, `structure`, `annotations`.
Les étiquettes sont placées automatiquement hors des zones de débattement des portes et des symboles.
Les cotes des épaisseurs de murs sont en centimètres (« 20 »), les autres en mètres (« 3,74 »).

### D-009 — Électricité : fidélité au prototype
Le prototype « Module Électrification » est archivé dans `docs/reference/`. Le test
`test_identique_au_prototype_execute` exécute son JavaScript (Node) sur les mêmes pièces et les mêmes
longueurs, et compare circuits, sections, états, différentiels et bilan. Une sortie figée sert quand Node est absent.
Règles reprises telles quelles du prototype : véranda = « extérieur » (1 point lumineux / 15 m²),
Ib des circuits spécialisés = P / U (P / (U cos φ) pour les climatiseurs), surfaces = surfaces nettes du plan.
Le WC, le placard et le rangement ne reçoivent pas de prise ; placard et rangement n'ont pas de point lumineux.

### D-010 — Électricité : placement des symboles
- Tableau à 0,55 m de la porte d'entrée, côté intérieur de la façade du séjour.
- Prises spécialisées : plaque, four, lave-vaisselle en cuisine ; lave-linge et pompe au garage, sinon en cuisine ;
  chauffe-eau en salle de bains ; climatiseurs dans leur pièce. Elles s'intercalent parmi les prises normales.
- Prises de la véranda : uniquement contre la façade. Interrupteur du dégagement : à côté de la baie du séjour.
- Si aucun point d'un circuit n'existe sur le plan, la longueur par défaut est la plus grande longueur calculée.

### D-011 — Structure : murs porteurs et largeurs reprises
- Semelles filantes sous les murs extérieurs et les refends porteurs ; les cloisons de 10 cm sont posées sur le dallage.
- 2 pans : les fermes portent de façade à façade ; chaque façade reprend la demi-profondeur + le débord ;
  les pignons reprennent une demi-travée de fermes (0,60 m). 4 pans : murs latéraux à D/4 + débord.
  Terrasse : dalle portant dans le sens de la profondeur entre façades et murs du couloir.
- Le poids propre de la semelle n'est pas ajouté (formule du § 6.4 appliquée telle quelle).
- Poteaux : à chaque extrémité de mur (angles et jonctions, cloisons comprises) et de part et d'autre
  des ouvertures de plus de 1,80 m.

### D-012 — Toiture
Le garage reçoit son propre pan (fermes sur sa profondeur). Bois d'une ferme : 2 arbalétriers + entrait +
poinçon + contrefiches (≈ un rampant). Terrasse : pas de débord, acrotère sur le périmètre, gouttières nulles.

### D-013 — Métré
- Fouilles : semelle + 0,30 m de sur-profondeur. Maçonnerie : hauteur = HSP (sous le chaînage), ouvertures déduites.
- Le béton armé regroupe chaînages, poteaux, linteaux et dalle de toiture ; l'acier de la dalle suit le ratio 120 kg/m³.
- Ciment et sable comptent aussi le mortier ; le dallage compte dans le béton (ciment, granulats).
- Carrelage : toutes les surfaces nettes sauf le garage (véranda comprise). Peinture : 2 faces de murs + plafonds.
- Prix de départ dans `app/moteurs/prix_defaut.py`, en USD, « indicatif — à mettre à jour ».
  Si le programme demande une autre devise, un avertissement le signale ; aucune conversion n'est faite.

### D-014 — Calques par défaut du plan
`plan.svg` sans paramètre affiche murs, textes, cotes et annotations ; `elec`, `structure` et `mobilier`
s'activent par `?calques=`. Le placement des étiquettes tient toujours compte des symboles électriques.

### D-015 — Comptes et rôles
L'inscription publique crée toujours un compte `constructeur`. L'email donné dans `ADMIN_EMAIL` devient
`admin` à son inscription ; l'admin attribue ensuite les rôles `ingenieur` (avec numéro d'ordre) via
`PUT /api/admin/utilisateurs/{id}`. Mots de passe hachés avec bcrypt ; jetons JWT HS256 de 24 h (`JWT_DUREE_H`).

### D-016 — Droits sur les projets
Un constructeur ne voit que ses projets. Ingénieurs et administrateurs lisent tous les projets (pour les
vérifier) ; seuls le propriétaire et l'admin modifient ou suppriment.

### D-017 — Modification du programme
`PUT /api/projets/{id}/programme` recalcule toute la chaîne sans auto-correction IA (l'utilisateur a choisi ses
valeurs). Les validations existantes restent en base mais `encore_valide` passe à faux dès que l'empreinte change.

### D-018 — Base de données
Au démarrage, les tables manquantes sont créées (`AUTO_CREATE_TABLES=1`, défaut) et la table des prix est
amorcée. En production, mettre `AUTO_CREATE_TABLES=0` et lancer `alembic upgrade head` (migration initiale fournie).
Les champs JSON sont en JSONB sous PostgreSQL. Ajout d'une colonne `remarques` (ambiguïtés de l'interprétation)
et `version` (incrémentée à chaque modification) sur `Projet`, et `utilisateur_id` sur `Rendu` (quotas).

### D-019 — Connecteur Claude : le SDK gère les nouvelles tentatives
`apiconnect.claude` passe par le SDK `anthropic` (délai 60 s, 2 nouvelles tentatives intégrées au SDK).
`apiconnect.http` (httpx, 2 nouvelles tentatives à attente exponentielle sur 429/5xx/réseau, `Retry-After`
respecté) sert à Nano Banana. Les erreurs sont traduites en `IANonConfiguree` (clé absente ou refusée),
`IAIndisponible` (réseau, surcharge, 5xx : secours immédiat) et `ReponseInvalide` (sortie inexploitable :
nouvelle tentative, puis secours). Seuls la méthode, l'hôte, le chemin et le statut sont journalisés, jamais
les en-têtes. Un test parcourt les fichiers suivis par git à la recherche de clés réelles.

### D-020 — Double protection des données de terrain
Le connecteur recopie `resistance_terre`, `portance_sol` et `portance_mesuree` d'origine dans toute correction
proposée, et l'orchestrateur refuse de toute façon une correction qui toucherait un champ hors liste blanche.
Les dimensions du terrain ne sont pas corrigeables non plus.

### D-021 — « Expliquer » sans clé
Sans clé ou si Claude échoue, `POST /api/projets/{id}/expliquer` renvoie le texte du moteur (titre, détail,
référence ; pour un circuit, protection, section, longueur et chute de tension) avec `source: "regles"`.
`element_id` accepte un identifiant de contrôle (`ELEC-DU-C4`), un numéro de circuit (`C4`) ou sa clé (`ecl-1`).
Claude reçoit l'élément et les hypothèses de son module ; sa réponse est tronquée à 120 mots. L'appel est
ajouté au journal IA sans changer la date de modification ni l'empreinte du projet.

### D-022 — API Nano Banana relue le 2026-10-18
La page officielle confirme l'API `interactions` décrite au § 8 (modèle par défaut `gemini-nano-banana-2.1`,
`image_size` en majuscules). L'analyseur prend la dernière image de `steps[].content[]` (comme `output_image`
du SDK), accepte aussi `output_image`, l'ancien format `inline_data` et ignore une éventuelle copie de l'entrée.
Styles : `plan_meuble`, `iso_coupe`, `facade`, `perspective`.

### D-023 — Dates en UTC explicite
SQLite rend les dates sans fuseau ; l'API les renvoie toujours avec `+00:00`.

### D-024 — Relancer la génération sur un projet existant
`POST /api/projets/generer` accepte `projet_id` : la barre IA d'un projet existant relance tout le pipeline
(interprétation, calcul, auto-correction) sur ce projet au lieu d'en créer un nouveau. La version est incrémentée,
le journal IA est complété et les signatures existantes deviennent caduques (l'empreinte change).

### D-025 — Interface sans bibliothèque de routage ni de composants
Navigation par fragment (`#/projets/12/electricite`), état local React, CSS maison à variables. Bundle initial
≈ 50 Ko gzip, chaque onglet chargé à la demande. Les calques du plan sont redemandés au serveur (le placement des
étiquettes dépend des calques affichés) et mis en cache côté navigateur ; le calque `mobilier`, encore vide,
n'est pas proposé. Les lectures sont retentées 2 fois sur coupure réseau ; les écritures ne le sont pas
(pas de double création), l'erreur est affichée avec un bouton « Réessayer ».

### D-026 — « Bon pour exécution » avant le lot 10
Le bouton est désactivé tant que les six modules ne sont pas tous signés. En attendant le dossier PDF du lot 10,
il télécharge le rapport texte.

### D-027 — Tests e2e
Playwright lance l'API (SQLite jetable, sans clé IA) et Vite ; le parcours tourne sur un écran de bureau et un
téléphone (Pixel 7). `E2E_PYTHON` désigne l'interpréteur Python qui a les dépendances du backend.
`CAPTURES=1 npx playwright test captures` régénère les captures de revue visuelle.
