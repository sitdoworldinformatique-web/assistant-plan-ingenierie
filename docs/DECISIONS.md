# Décisions de développement

Chaque choix non couvert par le cahier des charges est noté ici (option la plus simple et la plus sûre).

## Avancement des lots
| Lot | État |
|---|---|
| 0 | fait — `docker compose up` sert la page (5173) et `/api/sante` (8000) |
| 1 | fait — 15 phrases de test interprétées par l'analyseur par règles |
| 2 | fait — plan coté du cas de référence, golden SVG, captures dans `docs/captures/` |

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
