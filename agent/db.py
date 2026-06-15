from datetime import datetime, timezone, timedelta
from typing import Optional

BRT = timezone(timedelta(hours=-3))

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
            "updated_at": datetime.now(BRT),
        }, merge=True)
    except Exception as e:
        print(f"[db] erro ao salvar conversa: {e}")


def save_lead(session_id: str, lead: dict) -> None:
    try:
        _get_db().collection("leads").document(session_id).set({
            **lead,
            "session_id": session_id,
            "captured_at": datetime.now(BRT),
            "status": "novo",
        })
    except Exception as e:
        print(f"[db] erro ao salvar lead: {e}")


def load_conversation(session_id: str) -> list:
    try:
        doc = _get_db().collection("conversations").document(session_id).get()
        return doc.to_dict().get("messages", []) if doc.exists else []
    except Exception as e:
        print(f"[db] erro ao carregar conversa: {e}")
        return []


def load_session_data(session_id: str) -> tuple[list, bool]:
    """Returns (messages, greeted_today). Single Firestore read."""
    try:
        doc = _get_db().collection("conversations").document(session_id).get()
        if not doc.exists:
            return [], False
        data = doc.to_dict() or {}
        today = datetime.now(BRT).strftime("%Y-%m-%d")
        greeted_today = data.get("greeted_date") == today
        return data.get("messages", []), greeted_today
    except Exception as e:
        print(f"[db] erro ao carregar sessão: {e}")
        return [], False


def mark_greeted(session_id: str) -> None:
    try:
        today = datetime.now(BRT).strftime("%Y-%m-%d")
        _get_db().collection("conversations").document(session_id).set(
            {"greeted_date": today}, merge=True
        )
    except Exception as e:
        print(f"[db] erro ao marcar saudação: {e}")


def update_lead(session_id: str, lead: dict) -> None:
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
