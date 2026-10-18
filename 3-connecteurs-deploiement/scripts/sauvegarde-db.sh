#!/usr/bin/env bash
# Sauvegarde PostgreSQL compressée + images de rendus. À lancer chaque nuit (cron, voir DEPLOIEMENT.md).
# Usage : sauvegarde-db.sh [dossier_de_destination]   (défaut : ./sauvegardes)
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:-./sauvegardes}"
GARDER_JOURS="${GARDER_JOURS:-14}"
HORODATAGE="$(date -u +%Y%m%dT%H%M%SZ)"
COMPOSE=(docker compose -f docker-compose.prod.yml)
mkdir -p "$DEST"
umask 077
"${COMPOSE[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$DEST/db-$HORODATAGE.sql.gz"
"${COMPOSE[@]}" exec -T backend tar -C /srv/donnees -czf - rendus > "$DEST/rendus-$HORODATAGE.tar.gz"
# Une sauvegarde vide ou tronquée ne doit pas passer inaperçue.
gzip -t "$DEST/db-$HORODATAGE.sql.gz"
[ "$(stat -c %s "$DEST/db-$HORODATAGE.sql.gz")" -gt 1000 ] || { echo "Sauvegarde suspecte (trop petite)" >&2; exit 1; }
find "$DEST" -name 'db-*.sql.gz' -mtime +"$GARDER_JOURS" -delete
find "$DEST" -name 'rendus-*.tar.gz' -mtime +"$GARDER_JOURS" -delete
echo "Sauvegarde écrite : $DEST/db-$HORODATAGE.sql.gz"
