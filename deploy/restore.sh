#!/usr/bin/env bash
# Restore a backup made by backup.sh (docs/deploy.md, 9). DESTRUCTIVE: replaces the database.
#   deploy/restore.sh condoos-20261110T033000Z.sql.gz.enc
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . deploy/.env.production; set +a
name="${1:?nome do arquivo em s3://\$S3_BUCKET/backups/}"
read -r -p "Isto APAGA o banco atual e restaura ${name}. Digite RESTAURAR para seguir: " ok
[ "$ok" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }

# Download first (streamed to a file this user owns), so a failed download changes nothing.
file=$(mktemp)
trap 'rm -f "$file"' EXIT
docker run --rm \
  -e AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION=sa-east-1 \
  amazon/aws-cli:2.27.0 s3 cp "s3://${S3_BUCKET}/backups/${name}" - --only-show-errors > "$file"
[ -s "$file" ] || { echo "Backup vazio ou não encontrado."; exit 1; }

compose="docker compose -f docker-compose.prod.yml --env-file deploy/.env.production"
$compose stop api worker web
$compose exec -T postgres psql -U postgres -c "DROP DATABASE condoos WITH (FORCE);" -c "CREATE DATABASE condoos;"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in "$file" \
  | gunzip | $compose exec -T postgres psql -U postgres -d condoos -v ON_ERROR_STOP=1 -q
$compose up -d
echo "Restaurado: ${name}"
