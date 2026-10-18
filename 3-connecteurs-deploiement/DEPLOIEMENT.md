# Déploiement en production

Deux voies : un **VPS Ubuntu** avec Docker Compose (recommandé, tout est dans ce dépôt) ou un **hébergeur géré** (Render, Railway).
Rien de secret n'est versionné : toutes les clés vivent dans `.env` (VPS) ou dans les variables de l'hébergeur.

## 1. Prérequis (VPS Ubuntu 22.04 ou 24.04)

- 2 Go de RAM minimum, 20 Go de disque ; un nom de domaine dont l'enregistrement A pointe vers l'IP du serveur.
- Ports 80 et 443 ouverts (`sudo ufw allow 80,443/tcp && sudo ufw allow OpenSSH && sudo ufw enable`).
- Docker et le plugin Compose :
  ```bash
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker $USER   # puis se reconnecter
  ```

## 2. Récupérer le code et configurer

```bash
git clone <URL-du-dépôt> assistant-plan-ingenierie
cd assistant-plan-ingenierie/3-connecteurs-deploiement
cp .env.example .env && chmod 600 .env
```

Remplir `.env` :

| Variable | Rôle |
|---|---|
| `DOMAINE` | nom de domaine public (sans `https://`) |
| `POSTGRES_PASSWORD` | mot de passe de la base (`openssl rand -hex 24`) |
| `JWT_SECRET` | clé de signature des sessions, 32 caractères minimum (`openssl rand -hex 32`). L'API **refuse de démarrer** en production sans elle. |
| `ADMIN_EMAIL` | l'inscription avec cet email crée l'administrateur (prix, rôles, n° d'ordre des ingénieurs) |
| `ANTHROPIC_API_KEY` | facultative : sans elle, l'analyseur par règles interprète les descriptions |
| `GEMINI_API_KEY` | facultative : sans elle, les rendus d'images sont désactivés |

Ne jamais coller une clé dans un ticket, un message ou un fichier versionné.

## 3. Premier démarrage (HTTP seul) et certificat HTTPS

Le serveur nginx a besoin du certificat pour écouter en 443 ; on l'obtient donc en deux temps.

```bash
# a) démarrer avec la configuration HTTP seule (modèle nginx-http)
export NGINX_MODELE=nginx-http.conf.template
docker compose -f docker-compose.prod.yml up -d --build

# b) demander le certificat (remplacer l'email ; DOMAINE est lu dans .env)
set -a; . ./.env; set +a
docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot certbot \
  certonly --webroot -w /var/www/certbot -d "$DOMAINE" --email vous@exemple.cd --agree-tos --no-eff-email

# c) passer en HTTPS (modèle par défaut)
unset NGINX_MODELE
docker compose -f docker-compose.prod.yml up -d --force-recreate proxy
```

Le conteneur `certbot` renouvelle ensuite le certificat tout seul (vérification toutes les 12 h).

Vérifier : `curl https://$DOMAINE/api/sante` renvoie `{"etat":"ok",…}`, puis ouvrir `https://$DOMAINE` et créer le compte administrateur.

Le schéma de la base est créé par Alembic à chaque démarrage du conteneur `backend` (`alembic upgrade head`).

## 4. Mises à jour

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Les données (volumes `db-data` et `rendus`) sont conservées. Une validation d'ingénieur n'est annulée que si le programme
ou la version des moteurs change : après une mise à jour qui modifie un moteur, les modules concernés repassent
« à valider » (voir `docs/DECISIONS.md`).

## 5. Sauvegardes

`scripts/sauvegarde-db.sh` écrit un dump PostgreSQL compressé et une archive des images de rendus, vérifie qu'elles ne sont pas vides, et supprime celles de plus de 14 jours.

```bash
sudo crontab -e
# chaque nuit à 02:30 (heure du serveur) :
30 2 * * * cd /home/ubuntu/assistant-plan-ingenierie/3-connecteurs-deploiement && ./scripts/sauvegarde-db.sh /var/backups/assistant-plan >> /var/log/assistant-sauvegarde.log 2>&1
```

Copier régulièrement `/var/backups/assistant-plan` **hors du serveur** (autre machine, stockage objet).

Restauration :

```bash
gunzip -c db-AAAAMMJJTHHMMSSZ.sql.gz | docker compose -f docker-compose.prod.yml exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose -f docker-compose.prod.yml exec -T backend tar -C /srv/donnees -xzf - < rendus-AAAAMMJJTHHMMSSZ.tar.gz
```

À tester une fois sur un serveur de secours avant d'en avoir besoin.

## 6. Exploitation

- Journaux : `docker compose -f docker-compose.prod.yml logs -f backend`. Les clés API n'y apparaissent jamais (seuls l'hôte et le chemin des appels sortants sont journalisés).
- État : `docker compose -f docker-compose.prod.yml ps` ; le conteneur `backend` expose un contrôle de santé sur `/api/sante`.
- Quota des rendus d'images : `RENDUS_MAX_PAR_JOUR` par utilisateur (jour UTC).
- Connexions lentes : nginx compresse en gzip et met en cache les fichiers à nom haché (1 an) ; le chargement initial pèse environ 50 Ko compressés.

## 7. Variante hébergeur géré (Render, Railway)

Le dépôt contient deux Dockerfile (contexte de build = **racine du dépôt**) : `2-backend/Dockerfile` et `1-frontend/Dockerfile`.

1. Créer une base PostgreSQL gérée et noter son URL au format SQLAlchemy : `postgresql+psycopg://utilisateur:motdepasse@hôte:5432/base`.
2. **Service API** (Docker, fichier `2-backend/Dockerfile`) avec les variables : `ENVIRONNEMENT=production`, `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `CORS_ORIGINS=https://<domaine-du-front>`, `AUTO_CREATE_TABLES=0`, et si besoin `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`. Commande de démarrage :
   `sh -c "alembic upgrade head && exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT:-8000} --timeout 120"`.
   Ajouter un disque persistant monté sur `/srv/donnees/rendus` avec `STOCKAGE_RENDUS=/srv/donnees/rendus` (sinon les images de rendus sont perdues à chaque déploiement).
3. **Service web** (Docker, `1-frontend/Dockerfile`) : l'interface appelle `/api` en chemin relatif, il faut donc que `/api/*` soit routé vers le service API (règle de réécriture/proxy de l'hébergeur) ou placer les deux derrière le même domaine.
4. Activer les sauvegardes automatiques de la base de l'hébergeur.

## 8. Contrôle avant ouverture aux utilisateurs

- [ ] `https://<domaine>/api/sante` répond et `ia_texte_configuree` et `ia_image_configuree` reflètent les clés configurées.
- [ ] Le compte `ADMIN_EMAIL` est créé et les prix (page Administration) sont renseignés.
- [ ] Un ingénieur a son rôle et son n° d'ordre renseignés ; une signature de test est visible sur le rapport.
- [ ] Une sauvegarde manuelle a été lancée et restaurée sur une machine de test.
- [ ] Les exports PDF/DXF/XLSX portent « À valider par un ingénieur qualifié » tant que les six modules ne sont pas signés.
