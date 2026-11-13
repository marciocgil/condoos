#!/usr/bin/env bash
# Zera os dados para um novo teste do zero (D131). Rodar no servidor: deploy/reset.sh
# Apaga condomínios, administradoras, documentos (banco e S3, prefixo cond/), análises,
# auditoria e trilha. Mantém as contas das pessoas, os papéis da equipe CondoOS, os índices
# do BCB e as versões dos prompts dos agentes. Faz o backup cifrado antes.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . deploy/.env.production; set +a
compose() { docker compose -f docker-compose.prod.yml --env-file deploy/.env.production "$@"; }

echo "Isto APAGA todos os condomínios, documentos, análises e a trilha de ${APP_DOMAIN}."
echo "Ficam: as contas das pessoas e o acesso da equipe CondoOS (sem condomínios)."
read -r -p "Para confirmar, digite o endereço do site (${APP_DOMAIN}): " typed
if [ "$typed" != "$APP_DOMAIN" ]; then
  echo "Não confere. Nada foi feito."
  exit 1
fi

echo "1/4 Backup antes de apagar..."
deploy/backup.sh
echo "2/4 Parando o site e a fila..."
compose stop web worker
echo "3/4 Apagando os dados..."
compose exec -T api python -m app.platform reset-data "$APP_DOMAIN"
echo "4/4 Subindo de novo..."
compose up -d
echo "Pronto. Entre em https://${APP_DOMAIN} e comece pela Carteira (Novo condomínio)."
