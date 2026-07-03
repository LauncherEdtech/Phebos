"""Painéis web: métricas do vendedor (link mágico) e registros do admin.

HTML autocontido (CSS inline, sem JS externo) — leve o bastante para
abrir bem no navegador do celular, que é onde o vendedor vive.
"""

import html
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .i18n import DEFAULT_LANG, status_label, t
from .models import format_money
from .storage import Storage

STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       background: #f4f6f8; color: #1a2430; padding: 16px; max-width: 720px;
       margin: 0 auto; }
@media (prefers-color-scheme: dark) {
  body { background: #101418; color: #e8edf2; }
  .card, table { background: #1a2129 !important; }
  td, th { border-color: #2a333d !important; }
}
h1 { font-size: 1.3rem; margin: 8px 0 16px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
         gap: 12px; margin-bottom: 24px; }
.card { background: #fff; border-radius: 12px; padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.card .label { font-size: .75rem; opacity: .7; text-transform: uppercase;
               letter-spacing: .04em; }
.card .value { font-size: 1.4rem; font-weight: 700; margin-top: 4px; }
h2 { font-size: 1rem; margin: 20px 0 8px; }
table { width: 100%; border-collapse: collapse; background: #fff;
        border-radius: 12px; overflow: hidden; font-size: .9rem; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid #edf0f3; }
th { font-size: .72rem; text-transform: uppercase; letter-spacing: .04em;
     opacity: .65; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px;
         font-size: .75rem; font-weight: 600; }
.b-pendente { background: #fff3cd; color: #7a5d00; }
.b-pago, .b-confirmado { background: #d5f5dd; color: #14652c; }
.b-cancelado { background: #e8e8e8; color: #555; }
.b-valor_divergente, .b-sem_cobranca { background: #ffe0e0; color: #8f1d1d; }
.empty { opacity: .6; padding: 16px; }
footer { margin-top: 28px; font-size: .75rem; opacity: .5; text-align: center; }
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head>"
            f"<body>{body}<footer>PixZap 💸</footer></body></html>")


def _badge(kind: str, label: str) -> str:
    return f"<span class='badge b-{html.escape(kind)}'>{html.escape(label)}</span>"


def render_seller_panel(storage: Storage, lang: str = DEFAULT_LANG,
                        tz_name: str = "America/Sao_Paulo") -> str:
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc = day_start.astimezone(timezone.utc).isoformat(timespec="seconds")
    week_utc = (day_start - timedelta(days=6)).astimezone(timezone.utc).isoformat(timespec="seconds")

    paid_today = storage.paid_charges_since(today_utc)
    paid_week = storage.paid_charges_since(week_utc)
    pending = storage.pending_charges()

    cards = ""
    for label_key, value in (
        ("panel_received_today", format_money(sum(c.amount_cents for c in paid_today))),
        ("panel_received_7d", format_money(sum(c.amount_cents for c in paid_week))),
        ("panel_pending", f"{len(pending)} • {format_money(sum(c.amount_cents for c in pending))}"),
    ):
        cards += (f"<div class='card'><div class='label'>{html.escape(t(lang, label_key))}</div>"
                  f"<div class='value'>{html.escape(value)}</div></div>")

    charges = storage.recent_charges(30)
    if charges:
        rows = "".join(
            f"<tr><td>#{c.id}</td><td>{html.escape(c.description or '—')}</td>"
            f"<td>{html.escape(format_money(c.amount_cents))}</td>"
            f"<td>{_badge(c.status.value, status_label(lang, c.status.value))}</td></tr>"
            for c in charges)
        charges_html = f"<table><tr><th>#</th><th></th><th></th><th></th></tr>{rows}</table>"
    else:
        charges_html = f"<div class='card empty'>{html.escape(t(lang, 'panel_empty'))}</div>"

    payments = storage.recent_payments(20)
    if payments:
        rows = "".join(
            f"<tr><td>{html.escape((p['received_at'] or '')[:10])}</td>"
            f"<td>{html.escape(p['payer_name'] or p['description'] or '—')}</td>"
            f"<td>{html.escape(format_money(p['amount_cents']))}</td>"
            f"<td>{_badge(p['outcome'], p['outcome'].replace('_', ' '))}</td></tr>"
            for p in payments)
        payments_html = f"<table><tr><th></th><th></th><th></th><th></th></tr>{rows}</table>"
    else:
        payments_html = f"<div class='card empty'>{html.escape(t(lang, 'panel_empty'))}</div>"

    body = (f"<h1>💸 {html.escape(t(lang, 'panel_title'))}</h1>"
            f"<div class='cards'>{cards}</div>"
            f"<h2>{html.escape(t(lang, 'panel_charges'))}</h2>{charges_html}"
            f"<h2>{html.escape(t(lang, 'panel_payments'))}</h2>{payments_html}")
    return _page(t(lang, "panel_title"), body)


def render_expired(lang: str = DEFAULT_LANG) -> str:
    return _page(t(lang, "panel_title"),
                 f"<div class='card empty'>{html.escape(t(lang, 'panel_expired'))}</div>")


def render_admin_panel(storage: Storage) -> str:
    """Registros completos para o administrador (sempre pt-BR)."""
    charges = storage.recent_charges(100)
    payments = storage.recent_payments(100)
    pending = storage.pending_charges()

    total_paid = sum(c.amount_cents for c in charges if c.status.value == "pago")
    alerts = [p for p in payments if p["outcome"] in ("valor_divergente", "sem_cobranca")]

    cards = ""
    for label, value in (
        ("Cobranças (últimas 100)", str(len(charges))),
        ("Pagas (valor)", format_money(total_paid)),
        ("Pendentes", str(len(pending))),
        ("⚠️ Alertas de conciliação", str(len(alerts))),
    ):
        cards += (f"<div class='card'><div class='label'>{html.escape(label)}</div>"
                  f"<div class='value'>{html.escape(value)}</div></div>")

    charge_rows = "".join(
        f"<tr><td>#{c.id}</td><td>{html.escape((c.created_at or '')[:16])}</td>"
        f"<td>{html.escape(c.description or '—')}</td>"
        f"<td>{html.escape(format_money(c.amount_cents))}</td>"
        f"<td>{html.escape(c.provider)}</td><td>{html.escape(c.txid)}</td>"
        f"<td>{_badge(c.status.value, c.status.value)}</td></tr>"
        for c in charges) or "<tr><td class='empty' colspan='7'>vazio</td></tr>"

    payment_rows = "".join(
        f"<tr><td>{html.escape((p['received_at'] or '')[:16])}</td>"
        f"<td>{html.escape(p['txid'])}</td>"
        f"<td>{html.escape(format_money(p['amount_cents']))}</td>"
        f"<td>{html.escape(p['payer_name'] or '—')}</td>"
        f"<td>{'#' + str(p['charge_id']) if p['charge_id'] else '—'}</td>"
        f"<td>{_badge(p['outcome'], p['outcome'].replace('_', ' '))}</td></tr>"
        for p in payments) or "<tr><td class='empty' colspan='6'>vazio</td></tr>"

    body = (
        "<h1>🛠️ PixZap — Admin</h1>"
        f"<div class='cards'>{cards}</div>"
        "<h2>Cobranças</h2><table><tr><th>#</th><th>Criada</th><th>Descrição</th>"
        f"<th>Valor</th><th>PSP</th><th>txid</th><th>Status</th></tr>{charge_rows}</table>"
        "<h2>Pagamentos (webhooks)</h2><table><tr><th>Recebido</th><th>txid</th>"
        f"<th>Valor</th><th>Pagador</th><th>Cobrança</th><th>Conciliação</th></tr>{payment_rows}</table>"
    )
    return _page("PixZap Admin", body)
