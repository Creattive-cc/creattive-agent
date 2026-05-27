"""
agent/memory.py — Gerenciamento de memória conversacional.
Responsabilidade: manter histórico de mensagens por session_id, com janela de contexto configurável.
"""

from typing import List, Dict
from collections import defaultdict

_MAX_MESSAGES = 20


class ConversationMemory:
    def __init__(self):
        self._store: Dict[str, List[dict]] = defaultdict(list)

    def add_message(self, session_id: str, role: str, text: str) -> None:
        history = self._store[session_id]
        history.append({"role": role, "parts": [text]})
        if len(history) > _MAX_MESSAGES:
            # descarta as mensagens mais antigas, mantendo as _MAX_MESSAGES mais recentes
            self._store[session_id] = history[-_MAX_MESSAGES:]

    def get_history(self, session_id: str) -> List[dict]:
        return list(self._store[session_id])

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
