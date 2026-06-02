"""
agent/db.py — Persistência de conversas e leads no Cloud Firestore.
"""

from datetime import datetime, timezone
from typing import Optional

_db = None


def _get_db():
    global _db
    if _db is None:
        from google.cloud import firestore
        _db = firestore.Client()
    return _db


def save_conversation(session_id: str, messages: list) -> None:
    try:
        _get_db().collection("conversations").document(session_id).set({
            "messages": messages,
            "updated_at": datetime.now(timezone.utc),
        })
    except Exception as e:
        print(f"[db] erro ao salvar conversa: {e}")


def save_lead(session_id: str, lead: dict) -> None:
    try:
        _get_db().collection("leads").document(session_id).set({
            **lead,
            "session_id": session_id,
            "captured_at": datetime.now(timezone.utc),
            "status": "novo",
        })
    except Exception as e:
        print(f"[db] erro ao salvar lead: {e}")


def update_lead(session_id: str, lead: dict) -> None:
    """Atualiza campos do lead preservando captured_at e status existentes."""
    try:
        _get_db().collection("leads").document(session_id).update(lead)
    except Exception as e:
        print(f"[db] erro ao atualizar lead: {e}")


def get_lead(session_id: str) -> Optional[dict]:
    try:
        doc = _get_db().collection("leads").document(session_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[db] erro ao buscar lead: {e}")
        return None
