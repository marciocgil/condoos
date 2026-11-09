#!/usr/bin/env bash
# Daily encrypted backup of the database to S3 São Paulo (docs/deploy.md, 9).
# Cron (user condoos):  30 3 * * *  /home/condoos/condoos/deploy/backup.sh >> /home/condoos/backup.log 2>&1
# The bucket's lifecycle rule deletes backups/ after 30 days.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . deploy/.env.production; set +a

stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="/tmp/condoos-${stamp}.sql.gz.enc"
docker compose -f docker-compose.prod.yml --env-file deploy/.env.production exec -T postgres \
  pg_dump -U postgres -d condoos --format=plain --no-owner \
  | gzip -9 \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_PASSPHRASE -out "$file"

docker run --rm -v /tmp:/tmp:ro \
  -e AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" -e AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION=sa-east-1 \
  amazon/aws-cli:2.27.0 s3 cp "$file" "s3://${S3_BUCKET}/backups/$(basename "$file")" --only-show-errors
rm -f "$file"
echo "$(date -u +%FT%TZ) backup ok $(basename "$file")"
