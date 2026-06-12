import os
import pathlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

_sa_path = pathlib.Path(__file__).parent / "service_account.json"

if os.getenv("K_SERVICE"):
    print("[AUTH] modo Cloud Run via ADC")
else:
    if _sa_path.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_sa_path)
        print(f"[AUTH] modo local via JSON ({_sa_path})")
    else:
        print("[AUTH] modo local — service_account.json não encontrado, tentando ADC")

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.core import CreattiveAgent

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "creattive")

_agent: CreattiveAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    _agent = CreattiveAgent()
    yield


app = FastAPI(lifespan=lifespan)


def _agent_instance() -> CreattiveAgent:
    if _agent is None:
        raise RuntimeError("Agent not initialized")
    return _agent


class ChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/admin/reindex")
async def reindex():
    agent = _agent_instance()
    result = agent.reindex_knowledge()
    return {"status": "reindexed", **result}


@app.post("/chat")
async def chat(req: ChatRequest):
    agent = _agent_instance()
    response = agent.responder(req.message, req.session_id)
    lead = agent.try_capture_lead(req.session_id)
    return {"response": response, "lead": lead}


@app.post("/webhook/whatsapp")
async def webhook_whatsapp(request: Request):
    if EVOLUTION_API_KEY:
        if request.headers.get("apikey") != EVOLUTION_API_KEY:
            raise HTTPException(status_code=403)

    payload = await request.json()

    if payload.get("event") != "messages.upsert":
        return JSONResponse({"status": "ignored"})

    data = payload.get("data", {})
    key = data.get("key", {})

    if key.get("fromMe"):
        return JSONResponse({"status": "ignored"})

    remote_jid = key.get("remoteJid", "")
    if remote_jid.endswith("@g.us"):
        return JSONResponse({"status": "ignored"})

    phone = remote_jid.split("@")[0]
    session_id = f"wa_{phone}"

    message_obj = data.get("message", {})
    text = message_obj.get("conversation") or message_obj.get("extendedTextMessage", {}).get("text")
    if not text:
        return JSONResponse({"status": "ignored"})

    agent = _agent_instance()
    response = agent.responder(text, session_id)
    agent.try_capture_lead(session_id, phone_hint=phone)

    if EVOLUTION_API_URL:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}",
                headers={"apikey": EVOLUTION_API_KEY},
                json={"number": phone, "text": response},
                timeout=30,
            )

    return JSONResponse({"status": "ok"})
