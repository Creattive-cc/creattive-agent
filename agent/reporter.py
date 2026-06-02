"""
agent/reporter.py — Gera e envia o resumo diário de atendimentos e leads.
"""

import os
import resend
from datetime import datetime, timezone, timedelta
from google.cloud import firestore

BRT = timezone(timedelta(hours=-3))


def _get_db():
    return firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "creattive-licitacoes-dev"))


def _is_today(ts) -> bool:
    if ts is None:
        return False
    today_start = datetime.now(BRT).replace(hour=0, minute=0, second=0, microsecond=0)
    if hasattr(ts, "tzinfo") and ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts >= today_start.astimezone(timezone.utc)


def build_report() -> dict:
    db = _get_db()

    convs_hoje = [
        d for d in db.collection("conversations").stream()
        if _is_today(d.to_dict().get("updated_at"))
        and len(d.to_dict().get("messages", [])) >= 2
    ]

    leads_docs = [
        d.to_dict() for d in db.collection("leads").stream()
        if _is_today(d.to_dict().get("captured_at"))
    ]

    return {
        "date": datetime.now(BRT).strftime("%d/%m/%Y"),
        "weekday": datetime.now(BRT).strftime("%A"),
        "total_conversations": len(convs_hoje),
        "total_leads": len(leads_docs),
        "leads": leads_docs,
    }


def _render_html(r: dict) -> str:
    def lead_card(lead: dict) -> str:
        nome    = lead.get("nome") or "—"
        empresa = lead.get("empresa") or "—"
        cnpj    = lead.get("cpf_cnpj") or "—"
        email   = lead.get("email") or "—"
        tel     = lead.get("telefone") or "—"
        status  = lead.get("status") or "novo"
        resumo  = lead.get("resumo") or ""

        resumo_block = (
            f'<tr><td colspan="2" style="padding-top:10px;">'
            f'<div style="background:#f9fafb;border-radius:6px;padding:12px;font-size:13px;'
            f'color:#374151;line-height:1.6;">{resumo}</div></td></tr>'
        ) if resumo else ""

        return f"""
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border:1px solid #e5e7eb;border-radius:8px;margin-bottom:12px;">
          <tr>
            <td style="padding:16px;">
              <div style="font-size:15px;font-weight:600;color:#111;">{nome}</div>
              <div style="color:#6b7280;font-size:13px;margin-bottom:10px;">{empresa} · {cnpj}</div>
              <table cellpadding="3" cellspacing="0" style="font-size:13px;width:100%;">
                <tr>
                  <td style="color:#6b7280;width:80px;">E-mail</td>
                  <td>{email}</td>
                  <td style="color:#6b7280;width:80px;">Telefone</td>
                  <td>{tel}</td>
                </tr>
                <tr>
                  <td style="color:#6b7280;">Status</td>
                  <td colspan="3">{status}</td>
                </tr>
                {resumo_block}
              </table>
            </td>
          </tr>
        </table>"""

    lead_section = "".join(lead_card(l) for l in r["leads"]) if r["leads"] \
        else '<p style="color:#6b7280;font-size:14px;">Nenhum lead capturado hoje.</p>'

    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  max-width:600px;margin:0 auto;padding:24px;color:#111;background:#fff;">

  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-bottom:2px solid #111;margin-bottom:24px;">
    <tr>
      <td>
        <div style="font-size:22px;font-weight:700;">LucIA · Resumo do Dia</div>
        <div style="color:#6b7280;font-size:14px;">{r["date"]}</div>
      </td>
    </tr>
  </table>

  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
    <tr>
      <td width="48%" style="background:#f9fafb;border-radius:8px;padding:20px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#111;">{r["total_conversations"]}</div>
        <div style="color:#6b7280;font-size:13px;margin-top:4px;">atendimento(s)</div>
      </td>
      <td width="4%"></td>
      <td width="48%" style="background:#f9fafb;border-radius:8px;padding:20px;text-align:center;">
        <div style="font-size:36px;font-weight:700;color:#111;">{r["total_leads"]}</div>
        <div style="color:#6b7280;font-size:13px;margin-top:4px;">lead(s) capturado(s)</div>
      </td>
    </tr>
  </table>

  <div style="font-size:15px;font-weight:600;margin-bottom:12px;">Leads do dia</div>
  {lead_section}

  <table width="100%" cellpadding="0" cellspacing="0"
         style="border-top:1px solid #e5e7eb;margin-top:24px;">
    <tr>
      <td style="padding-top:16px;font-size:12px;color:#9ca3af;">
        Creattive Agent · LucIA · Resumo automático das 18h
      </td>
    </tr>
  </table>

</body></html>"""


def send_daily_report() -> dict:
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        raise ValueError("RESEND_API_KEY não configurada")

    resend.api_key = api_key

    report = build_report()
    html   = _render_html(report)

    to_raw  = os.environ.get("REPORT_TO", "felipe.malveira@creattive.cc")
    to      = [e.strip() for e in to_raw.split(",") if e.strip()]
    from_   = os.environ.get("REPORT_FROM", "onboarding@resend.dev")
    subject = (
        f"LucIA · {report['date']} — "
        f"{report['total_conversations']} atendimento(s), "
        f"{report['total_leads']} lead(s)"
    )

    resp = resend.Emails.send({
        "from": from_,
        "to":   to,
        "subject": subject,
        "html": html,
    })

    print(f"[reporter] email enviado — id={resp.get('id')} | "
          f"conversas={report['total_conversations']} leads={report['total_leads']}")
    return {"ok": True, "email_id": resp.get("id"), **{k: report[k] for k in ("date", "total_conversations", "total_leads")}}
