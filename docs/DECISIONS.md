# Décisions de développement

Chaque choix non couvert par le cahier des charges est noté ici (option la plus simple et la plus sûre).

## Avancement des lots
| Lot | État |
|---|---|
| 0 | fait — `docker compose up` sert la page (5173) et `/api/sante` (8000) |

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
