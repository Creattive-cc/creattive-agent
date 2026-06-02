import os
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from agent.core import CreattiveAgent
from agent.db import save_lead

st.set_page_config(
    page_title="Creattive Agent",
    page_icon="💡",
    layout="wide",
)

st.markdown("""
<style>
/* User messages à direita */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    flex-direction: row-reverse;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"])
    [data-testid="stChatMessageContent"] {
    align-items: flex-end;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"])
    [data-testid="stMarkdownContainer"] p {
    text-align: right;
}
</style>
""", unsafe_allow_html=True)

# ── Session state init ────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "lead_captured" not in st.session_state:
    st.session_state.lead_captured = None

if "agent" not in st.session_state:
    with st.spinner("Inicializando agente..."):
        st.session_state.agent = CreattiveAgent()

agent: CreattiveAgent = st.session_state.agent

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Creattive Agent")
    st.divider()

    st.subheader("📄 Indexar PDFs")
    uploaded_files = st.file_uploader(
        "Carregar PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded_files:
        pdfs_dir = Path("data/pdfs")
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        indexed_sources = agent.rag_retriever.get_indexed_sources()

        for f in uploaded_files:
            if f.name not in indexed_sources:
                dest = pdfs_dir / f.name
                dest.write_bytes(f.read())
                with st.spinner(f"Indexando {f.name}…"):
                    agent.rag_retriever.index_pdf(str(dest))
                st.success(f"{f.name} indexado!")

    st.subheader("📚 Base de conhecimento")
    sources = agent.rag_retriever.get_indexed_sources()
    if sources:
        for source, count in sorted(sources.items()):
            st.caption(f"• **{source}** — {count} chunk{'s' if count != 1 else ''}")
    else:
        st.caption("Nenhum documento indexado.")

    st.divider()

    # ── Lead ─────────────────────────────────────────────────────────────────
    st.subheader("👤 Lead")
    lead = st.session_state.lead_captured
    if lead:
        st.success("Lead capturado")
        st.caption(f"**{lead.get('nome') or '—'}**")
        if lead.get("empresa"):
            st.caption(f"🏢 {lead['empresa']}")
        if lead.get("email"):
            st.caption(f"✉ {lead['email']}")
        if lead.get("telefone"):
            st.caption(f"📞 {lead['telefone']}")
        if lead.get("cpf_cnpj"):
            st.caption(f"📋 {lead['cpf_cnpj']}")
    else:
        if st.session_state.messages:
            st.caption("Nenhum lead capturado ainda.")
            with st.expander("Registrar manualmente"):
                with st.form("lead_form"):
                    nome = st.text_input("Nome completo *")
                    empresa = st.text_input("Empresa")
                    cpf_cnpj = st.text_input("CPF / CNPJ")
                    email = st.text_input("E-mail *")
                    telefone = st.text_input("Telefone *")
                    submitted = st.form_submit_button("Salvar", use_container_width=True)
                    if submitted:
                        if not (nome and email and telefone):
                            st.error("Nome, e-mail e telefone são obrigatórios.")
                        else:
                            lead_data = {
                                "nome": nome,
                                "empresa": empresa,
                                "cpf_cnpj": cpf_cnpj,
                                "email": email,
                                "telefone": telefone,
                                "origem": "manual",
                            }
                            save_lead(st.session_state.session_id, lead_data)
                            st.session_state.lead_captured = lead_data
                            st.rerun()
        else:
            st.caption("Inicie uma conversa para capturar leads.")

    st.divider()

    if st.button("🗑️ Limpar conversa", use_container_width=True):
        st.session_state.messages = []
        st.session_state.lead_captured = None
        st.session_state.session_id = str(uuid.uuid4())
        agent.clear_memory(st.session_state.session_id)
        st.rerun()

# ── Main chat ─────────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Digite sua mensagem…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("LucIA está pensando…"):
            response = agent.responder(prompt, st.session_state.session_id)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

    if not st.session_state.lead_captured:
        lead = agent.try_capture_lead(st.session_state.session_id)
        if lead:
            st.session_state.lead_captured = lead
            st.rerun()
