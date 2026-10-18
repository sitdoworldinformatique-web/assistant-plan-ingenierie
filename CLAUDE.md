# ASSISTANT PLAN INGÉNIERIE — mémo pour Claude Code

Spécification complète : `CAHIER_DES_CHARGES.md` (à relire avant toute évolution).
Décisions prises pendant le développement : `docs/DECISIONS.md` (à compléter à chaque choix non couvert).

## Produit
SaaS web : un constructeur décrit une maison en français → l'IA en tire un `Programme` →
des moteurs Python déterministes calculent plan, fondations, structure, toiture, électricité,
solaire, métré/devis → rapport de conformité → **un ingénieur relit et signe** module par module.
Marché : Afrique francophone (RDC), connexions lentes, prix en USD paramétrables.

## Règles non négociables
- `L'IA propose → les moteurs calculent et vérifient → l'ingénieur valide et signe`.
- Aucun LLM ne calcule une valeur de sécurité (section, ferraillage, semelle, calibre, chute de tension).
- Toutes les constantes normatives sont dans `2-backend/app/moteurs/normes.py`, jamais en dur dans un moteur.
- Moteurs = fonctions pures `calculer(programme, ...)` sans réseau ni base ; chacun renvoie `controles` et `hypotheses`.
- L'IA ne modifie jamais `resistance_terre`, `portance_sol`, `portance_mesuree`.
- Une validation est liée à l'empreinte SHA-256 (programme + version des moteurs) ; toute modification l'annule.
- Exports : « À valider par un ingénieur qualifié » tant que le module n'est pas signé.
- Images Nano Banana : présentation, non contractuelles, mention obligatoire.
- Aucune clé API dans le code, les logs ou le dépôt.

## Structure
- `1-frontend/` : React 18 + TypeScript + Vite.
- `2-backend/` : Python 3.12, FastAPI, Pydantic v2 ; `app/moteurs/` (calculs), `app/rendu/` (SVG, DXF, PDF, rapport).
- `3-connecteurs-deploiement/` : `connecteurs/apiconnect` (Claude, Nano Banana), Docker Compose, Nginx, scripts, `DEPLOIEMENT.md`.
  Le backend importe `apiconnect` via `PYTHONPATH`.

## Commandes
```bash
# Backend (depuis 2-backend/)
PYTHONPATH=.:../3-connecteurs-deploiement/connecteurs uvicorn app.main:app --reload
PYTHONPATH=.:../3-connecteurs-deploiement/connecteurs pytest -q
ruff check .

# Connecteurs (depuis 3-connecteurs-deploiement/connecteurs/)
pytest -q

# Frontend (depuis 1-frontend/)
npm install && npm run dev      # http://localhost:5173
npm test                        # Vitest
npm run build
E2E_PYTHON=python3 npx playwright test   # e2e : texte → plan → export SVG

# Tout en Docker (depuis 3-connecteurs-deploiement/)
docker compose up --build       # frontend :5173, API :8000/api/sante
```

## Lots (section 12) — avancement
Voir `docs/DECISIONS.md` § Avancement.
