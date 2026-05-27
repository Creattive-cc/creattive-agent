
from agent.gemini_client import GeminiClient
from agent.memory import ConversationMemory
from agent.prompts import build_system_prompt
from agent.rag import RAGRetriever


class CreattiveAgent:
    """
    The core of the Creattive AI agent, orchestrating the different components
    to generate responses.
    """

    def __init__(self):
        """Initializes the agent's components."""
        print("Initializing CreattiveAgent...")
        self.gemini_client = GeminiClient()
        self.memory = ConversationMemory()
        # RAGRetriever will automatically index knowledge if the DB is empty.
        self.rag_retriever = RAGRetriever()
        print("CreattiveAgent initialized successfully.")

    def responder(self, message: str, session_id: str) -> str:
        """
        Generates a response to a user message.

        Args:
            message (str): The user's message.
            session_id (str): The unique identifier for the conversation session.

        Returns:
            str: The agent's generated response.
        """
        # 1. Retrieve relevant context using RAG
        relevant_chunks = self.rag_retriever.search(query=message, k=5)

        # 2. Build the system prompt with the retrieved context
        system_prompt = build_system_prompt(relevant_chunks)

        # 3. Get conversation history
        history = self.memory.get_history(session_id)

        # 4. Generate response using Gemini client
        response_text = self.gemini_client.chat(system_prompt, history, message)

        # 5. Save the new turn to memory
        self.memory.add_message(session_id, "user", message)
        self.memory.add_message(session_id, "model", response_text)

        # 6. Return the response
        return response_text

    def clear_memory(self, session_id: str):
        """Clears the conversation history for a specific session."""
        self.memory.clear(session_id)
        print(f"Memory for session '{session_id}' has been cleared.")

