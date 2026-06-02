import os
from datetime import timezone, timedelta

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

import streamlit as st
from google.cloud import firestore

st.set_page_config(page_title="Leads · Creattive", page_icon="👥", layout="wide")

BRT = timezone(timedelta(hours=-3))

_STATUS_COLORS = {
    "novo":             "🔵",
    "em contato":       "🟡",
    "proposta enviada": "🟠",
    "fechado":          "🟢",
    "perdido":          "🔴",
}
_STATUS_OPTIONS = list(_STATUS_COLORS.keys())


@st.cache_resource
def _get_db():
    return firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "creattive-licitacoes-dev"))


def _load_leads():
    db = _get_db()
    docs = (
        db.collection("leads")
        .order_by("captured_at", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [{"_id": d.id, **d.to_dict()} for d in docs]


def _update_status(doc_id: str, status: str):
    _get_db().collection("leads").document(doc_id).update({"status": status})


def _fmt_date(ts) -> str:
    if ts is None:
        return "—"
    try:
        local = ts.astimezone(BRT)
        return local.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(ts)


# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_btn = st.columns([6, 1])
with col_title:
    st.title("👥 Leads")
with col_btn:
    st.write("")
    if st.button("🔄 Atualizar", use_container_width=True):
        st.rerun()

leads = _load_leads()

if not leads:
    st.info("Nenhum lead capturado ainda. Inicie uma conversa no chat.")
    st.stop()

st.caption(f"{len(leads)} lead(s) encontrado(s)")
st.divider()

# ── Listagem ──────────────────────────────────────────────────────────────────
for lead in leads:
    doc_id  = lead.get("_id", "")
    nome    = lead.get("nome") or "Sem nome"
    empresa = lead.get("empresa") or ""
    email   = lead.get("email") or "—"
    tel     = lead.get("telefone") or "—"
    cnpj    = lead.get("cpf_cnpj") or "—"
    origem  = lead.get("origem") or "automático"
    status  = lead.get("status") or "novo"
    resumo  = lead.get("resumo") or ""
    data    = _fmt_date(lead.get("captured_at"))
    icone   = _STATUS_COLORS.get(status, "⚪")

    header = f"{icone} **{nome}**"
    if empresa:
        header += f"  ·  {empresa}"
    header += f"  ·  {data}"

    with st.expander(header, expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**E-mail**\n\n{email}")
        c2.markdown(f"**Telefone**\n\n{tel}")
        c3.markdown(f"**CPF / CNPJ**\n\n{cnpj}")
        c4.markdown(f"**Origem**\n\n{origem}")

        st.write("")

        if resumo:
            st.markdown("**Resumo da conversa**")
            st.markdown(resumo)
        else:
            st.caption("Resumo não disponível.")

        st.write("")

        novo_status = st.selectbox(
            "Status",
            options=_STATUS_OPTIONS,
            index=_STATUS_OPTIONS.index(status) if status in _STATUS_OPTIONS else 0,
            key=f"status_{doc_id}",
        )
        if novo_status != status:
            _update_status(doc_id, novo_status)
            st.success(f"Status atualizado para **{novo_status}**")
            st.rerun()

    st.write("")
