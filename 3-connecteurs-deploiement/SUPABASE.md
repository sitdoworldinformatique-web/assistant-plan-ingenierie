# Utiliser Supabase comme base de données

Supabase fournit un PostgreSQL géré. L'application n'utilise que la base (via `DATABASE_URL`) : l'authentification, les
projets et les validations restent gérés par notre API. Pas de SDK Supabase dans l'application.

## 1. Créer le projet (à faire par vous, sur votre compte)
1. https://supabase.com/dashboard/new : nom `assistant-plan`, région la plus proche des utilisateurs, mot de passe de base
   fort (à garder dans un gestionnaire de mots de passe).
2. Une fois le projet prêt : **Connect** → **Session pooler** (port 5432, compatible IPv4) → copier l'URI.
3. Dans `3-connecteurs-deploiement/.env` (jamais dans le dépôt ni dans le chat) :
   ```
   DATABASE_URL=postgresql+psycopg://postgres.<ref>:<mot-de-passe>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
   ```
   Remplacez le préfixe `postgresql://` de l'URI copiée par `postgresql+psycopg://`.
4. Démarrer l'API : `alembic upgrade head` crée les tables (5 tables) puis active la sécurité par ligne (RLS) sans politique.
   Cela ferme l'API REST publique de Supabase : seule notre API accède aux données.

## 2. Ce qu'il ne faut pas faire
- Ne jamais mettre la clé `service_role` ni le mot de passe de la base dans le navigateur ou le code.
- Ne pas désactiver la RLS : sans elle, la clé publique (anon) pourrait lire les tables.

## 3. Images de rendus dans Supabase Storage
1. Dashboard Supabase → **Storage** → **New bucket** : nom `rendus`, **privé** (ne pas cocher « Public »).
2. **Project Settings → API** : copier l'URL du projet et la clé `service_role` (secrète) dans le `.env` du serveur :
   ```
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_SERVICE_KEY=<clé service_role>
   SUPABASE_BUCKET=rendus
   ```
3. Redémarrer l'API. Les nouvelles images partent dans le bucket ; les images déjà sur disque restent lisibles.
   Les images ne sont jamais publiques : l'API les relit avec la clé et les sert aux seuls membres du projet.
   Si Supabase ne répond pas, la génération échoue avec un message clair et rien n'est enregistré.

## 4. Sauvegardes
Supabase fait des sauvegardes quotidiennes (selon l'offre) ; `scripts/sauvegarde-db.sh` fonctionne aussi avec
`pg_dump "$DATABASE_URL"`.
