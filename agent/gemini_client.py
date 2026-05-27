"""
agent/gemini_client.py — Cliente Gemini via google-genai.
Responsabilidade: inicializar modelo, enviar prompts com histórico e retornar texto.
"""

import os
from typing import List

from google import genai
from google.genai import types

# This model name is compatible with the google.genai library
_MODEL_NAME = "gemini-2.5-flash"


class GeminiClient:
    def __init__(self):
        self._client = genai.Client(
            api_key=os.environ["GEMINI_API_KEY"],
        )

    def chat(
        self,
        system_prompt: str,
        history: List[dict],
        user_message: str,
    ) -> str:
        """
        Sends a message to the Gemini model and gets a response.
        This implementation is for the `google.genai` SDK.
        """
        # Convert history to the format expected by the new SDK
        contents = [
            types.Content(
                role=entry["role"],
                parts=[types.Part(text=p) for p in entry["parts"]],
            )
            for entry in history
        ]
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=user_message)],
            )
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )

        # The Client object has a `models` attribute to generate content
        response = self._client.models.generate_content(
            model=_MODEL_NAME,
            contents=contents,
            config=config,
        )
        return response.text
