# creattive-agent

Agente comercial conversacional da Creattive. Responde perguntas sobre produtos e serviços usando uma base de conhecimento (RAG), captura leads automaticamente e persiste histórico de conversas no Firestore.

Suporta dois canais: interface web via Streamlit e WhatsApp via Evolution API (webhook).

## Arquitetura

```
knowledge/          base de conhecimento em Markdown/PDF
agent/
  core.py           orquestrador principal (RAG + Gemini + captura de leads)
  rag.py            indexação e busca com ChromaDB + embeddings Vertex AI
  gemini_client.py  cliente Gemini via Vertex AI
  memory.py         memória conversacional por sessão
  db.py             persistência no Firestore (leads e conversas)
  lead_extractor.py extração incremental de dados do lead
  reporter.py       geração de resumo diário de atendimentos
app.py              interface Streamlit (canal web)
api.py              API FastAPI (canal WhatsApp + integração externa)
pages/
  1_Leads.py        dashboard de leads capturados
report_job.py       Cloud Run Job para envio do resumo por e-mail
```

## Pré-requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Projeto GCP com as APIs habilitadas: Vertex AI, Firestore, Cloud Storage
- Service account com permissões: `roles/aiplatform.user`, `roles/datastore.user`, `roles/storage.objectAdmin`

## Setup local

```bash
# Clonar e instalar dependências
git clone git@github.com:Creattive-cc/creattive-agent.git
cd creattive-agent
uv sync

# Configurar variáveis de ambiente
cp .env.example .env
# editar .env com os valores do projeto
```

### Variáveis de ambiente

| Variável | Descrição | Obrigatória |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | ID do projeto GCP | Sim |
| `GOOGLE_CLOUD_LOCATION` | Região (ex: `us-central1`) | Sim |
| `GOOGLE_APPLICATION_CREDENTIALS` | Caminho para o service account JSON (local) | Sim (local) |
| `GEMINI_API_KEY` | Chave da API Gemini (alternativa ao Vertex) | Não |
| `GCS_BUCKET` | Bucket GCS para persistir o índice ChromaDB | Não |
| `ENV` | `prod` ativa persistência GCS; padrão `dev` | Não |
| `EVOLUTION_API_URL` | URL da instância Evolution API | Não |
| `EVOLUTION_API_KEY` | Chave de autenticação da Evolution API | Não |
| `EVOLUTION_INSTANCE` | Nome da instância Evolution (padrão: `creattive`) | Não |
| `RESEND_API_KEY` | Chave da API Resend para envio de e-mail | Sim (relatório) |
| `REPORT_FROM` | Remetente do resumo diário (ex: `LucIA <lucia@creattive.cc>`) | Sim (relatório) |
| `REPORT_TO` | Destinatários do resumo diário, separados por vírgula | Sim (relatório) |

### Executar

```bash
# Interface Streamlit
uv run streamlit run app.py

# API FastAPI
uv run uvicorn api:app --host 0.0.0.0 --port 8080 --reload
```

## Base de conhecimento

Os arquivos em `knowledge/` (Markdown e PDF) são indexados automaticamente na primeira execução. Para reindexar após alterações, apague o diretório `/tmp/chroma` local ou o prefixo `chroma/` no bucket GCS.

## Deploy no Cloud Run

O projeto tem dois serviços independentes.

### Interface web (Streamlit)

```bash
gcloud builds submit \
  --project=SEU_PROJETO \
  --tag=gcr.io/SEU_PROJETO/creattive-agent:latest .

gcloud run deploy creattive-agent \
  --image=gcr.io/SEU_PROJETO/creattive-agent:latest \
  --platform=managed \
  --region=us-central1 \
  --set-env-vars=ENV=prod,GOOGLE_CLOUD_PROJECT=SEU_PROJETO,GCS_BUCKET=SEU_BUCKET \
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest
```

### API FastAPI (WhatsApp + REST)

```bash
gcloud builds submit \
  --project=SEU_PROJETO \
  --config=cloudbuild-api.yaml .

gcloud run deploy creattive-agent-api \
  --image=gcr.io/SEU_PROJETO/creattive-agent-api:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=1Gi \
  --set-env-vars=ENV=prod,GOOGLE_CLOUD_PROJECT=SEU_PROJETO,GCS_BUCKET=SEU_BUCKET \
  --set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest
```

### Job de relatório diário

```bash
gcloud run jobs deploy creattive-agent-report \
  --image=gcr.io/SEU_PROJETO/creattive-agent:latest \
  --region=us-central1 \
  --command=uv,run,python,report_job.py \
  --update-env-vars="^|^REPORT_FROM=LucIA <lucia@creattive.cc>" \
  --update-env-vars="^|^REPORT_TO=destinatario@empresa.com,outro@empresa.com" \
  --set-secrets=RESEND_API_KEY=RESEND_API_KEY:latest
```

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Envia mensagem e recebe resposta do agente |
| `POST` | `/webhook/whatsapp` | Webhook para receber mensagens do WhatsApp (Evolution API) |

### Exemplo `/chat`

```bash
curl -X POST https://SEU_SERVICO.run.app/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "sessao-123", "message": "Olá, quero saber sobre os serviços"}'
```

## Desenvolvimento

```bash
# Testes
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .
```

