"""
agent/lead_extractor.py — Extração estruturada de dados de lead a partir do histórico de conversa.
"""

import json
from typing import Optional

_EXTRACTION_PROMPT = """Analise o histórico de conversa abaixo e extraia dados de contato do cliente, se presentes.

Retorne APENAS um JSON com os campos abaixo (use null para campos não mencionados):
{{
  "nome": null,
  "empresa": null,
  "cpf_cnpj": null,
  "email": null,
  "telefone": null
}}

Se não houver NENHUM dado de contato na conversa, retorne o literal: null

Histórico:
{history}
"""

def extract_lead(history: list, gemini_client) -> Optional[dict]:
    if not history:
        return None

    history_text = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'LucIA'}: {m['parts'][0]}"
        for m in history
    )

    prompt = _EXTRACTION_PROMPT.format(history=history_text)

    try:
        raw = gemini_client.chat(
            system_prompt="Você é um extrator de dados. Retorne apenas JSON válido ou o literal null.",
            history=[],
            message=prompt,
        ).strip()

        if not raw or raw.lower() == "null":
            return None

        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1].removeprefix("json").strip() if len(parts) > 1 else raw

        data = json.loads(raw)
        if not isinstance(data, dict):
            return None

        # Exige nome + pelo menos um canal de contato (email ou telefone)
        has_nome = bool(data.get("nome"))
        has_contato = bool(data.get("email")) or bool(data.get("telefone"))
        if not (has_nome and has_contato):
            return None

        return data

    except Exception as e:
        print(f"[lead_extractor] erro: {e}")
        return None
