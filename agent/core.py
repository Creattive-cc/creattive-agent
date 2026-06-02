
from typing import Optional

from agent.db import save_conversation, save_lead
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
        self._leads_captured: set[str] = set()
        print("CreattiveAgent initialized successfully.")

    def responder(self, message: str, session_id: str) -> str:
        relevant_chunks = self.rag_retriever.search(query=message, k=5)
        system_prompt = build_system_prompt(relevant_chunks)
        history = self.memory.get_history(session_id)

        response_text = self.gemini_client.chat(system_prompt, history, message)

        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "model", response_text)

        save_conversation(session_id, self.memory.get_history(session_id))

        return response_text

    def try_capture_lead(self, session_id: str) -> Optional[dict]:
        """Tenta extrair e salvar dados de lead do histórico atual. Roda uma única vez por sessão."""
        if session_id in self._leads_captured:
            return None
        history = self.memory.get_history(session_id)
        if len(history) < 4:
            return None
        lead = extract_lead(history, self.gemini_client)
        if lead:
            lead["resumo"] = generate_summary(history, self.gemini_client)
            save_lead(session_id, lead)
            self._leads_captured.add(session_id)
            return lead
        return None

    def clear_memory(self, session_id: str):
        self.memory.clear(session_id)
        self._leads_captured.discard(session_id)
        print(f"Memory for session '{session_id}' has been cleared.")

