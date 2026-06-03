#!/bin/bash
# Setup local Evolution API instance
# Run after: docker compose -f docker-compose.evolution.yml up -d
#
# Usage:
#   ./evolution_setup.sh                         # sem webhook
#   ./evolution_setup.sh https://xxx.ngrok-free.app  # com webhook ngrok

BASE_URL="http://localhost:8080"
API_KEY="evolution-local-key"
INSTANCE="creattive"
WEBHOOK_URL="${1:-}"

echo "==> Aguardando Evolution API..."
until curl -s "$BASE_URL" > /dev/null 2>&1; do
  sleep 2
done
echo "    OK"

echo "==> Criando instância '$INSTANCE'..."
CREATE_RESULT=$(curl -s -X POST "$BASE_URL/instance/create" \
  -H "apikey: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"instanceName\": \"$INSTANCE\",
    \"integration\": \"WHATSAPP-BAILEYS\",
    \"qrcode\": true
  }")
echo "$CREATE_RESULT" | python3 -m json.tool

# Se instância já existe, ignora o erro e segue
if echo "$CREATE_RESULT" | grep -q "already exists\|already_exists"; then
  echo "    (instância já existe, seguindo...)"
fi

echo ""
echo "==> Conectando instância (gera QR code)..."
curl -s "$BASE_URL/instance/connect/$INSTANCE" \
  -H "apikey: $API_KEY" | python3 -m json.tool

echo ""
echo "==> Escaneie o QR code acima com o WhatsApp"
echo "    Ou acesse: http://localhost:8080/manager"

if [ -n "$WEBHOOK_URL" ]; then
  echo ""
  echo "==> Configurando webhook: $WEBHOOK_URL/webhook/whatsapp ..."
  curl -s -X POST "$BASE_URL/webhook/set/$INSTANCE" \
    -H "apikey: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"url\": \"$WEBHOOK_URL/webhook/whatsapp\",
      \"webhook_by_events\": false,
      \"webhook_base64\": false,
      \"events\": [\"messages.upsert\"]
    }" | python3 -m json.tool
  echo "    Webhook configurado. Suba a FastAPI local antes de testar."
else
  echo ""
  echo "    Para configurar webhook depois:"
  echo "    ./evolution_setup.sh https://SEU-NGROK.ngrok-free.app"
fi
