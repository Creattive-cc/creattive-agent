from typing import Optional

from agent.db import load_session_data, save_conversation, mark_greeted, save_lead, update_lead
from agent.gemini_client import GeminiClient
from agent.lead_extractor import extract_lead, generate_summary
from agent.memory import ConversationMemory
from agent.prompts import build_system_prompt
from agent.rag import RAGRetriever


class CreattiveAgent:
    def __init__(self):
        print("Initializing CreattiveAgent...")
        self.gemini_client = GeminiClient()
        self.memory = ConversationMemory()
        self.rag_retriever = RAGRetriever()
        self._leads_captured: dict[str, bool] = {}  # session_id -> completo?
        print("CreattiveAgent initialized successfully.")

    def responder(self, message: str, session_id: str) -> str:
        if not self.memory.get_history(session_id):
            saved, greeted = load_session_data(session_id)
            if saved:
                self.memory.seed(session_id, saved)
            is_first_message = not greeted
        else:
            is_first_message = False

        relevant_chunks = self.rag_retriever.search(query=message, k=5)
        history = self.memory.get_history(session_id)
        system_prompt = build_system_prompt(relevant_chunks, is_first_message=is_first_message)

        response_text = self.gemini_client.chat(system_prompt, history, message)

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "model", response_text)

        save_conversation(session_id, self.memory.get_history(session_id))
        if is_first_message:
            mark_greeted(session_id)

        return response_text

    _COMPLETE_FIELDS = ("nome", "empresa", "cpf_cnpj", "email", "telefone")

    def _lead_is_complete(self, lead: dict) -> bool:
        return all(lead.get(f) for f in self._COMPLETE_FIELDS)

    def try_capture_lead(self, session_id: str, phone_hint: Optional[str] = None) -> Optional[dict]:
        if self._leads_captured.get(session_id) is True:
            return None

        history = self.memory.get_history(session_id)
        if len(history) < 6:  # aguarda ao menos 3 turnos completos
            return None

        lead = extract_lead(history, self.gemini_client)
        if not lead:
            return None

        if phone_hint and not lead.get("telefone"):
            lead["telefone"] = phone_hint

        lead["resumo"] = generate_summary(history, self.gemini_client)

        is_first = session_id not in self._leads_captured
        if is_first:
            save_lead(session_id, lead)
        else:
            update_lead(session_id, lead)

        self._leads_captured[session_id] = self._lead_is_complete(lead)
        return lead

    def clear_memory(self, session_id: str):
        self.memory.clear(session_id)
        self._leads_captured.pop(session_id, None)
        print(f"Memory for session '{session_id}' has been cleared.")

    def reindex_knowledge(self) -> dict:
        self.rag_retriever.clear()
        self.rag_retriever.index_all_knowledge()
        sources = self.rag_retriever.get_indexed_sources()
        total = self.rag_retriever.count()
        return {"total_chunks": total, "sources": sources}

