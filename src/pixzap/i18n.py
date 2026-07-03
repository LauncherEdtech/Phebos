"""Catálogo de mensagens multilíngue (pt-BR padrão, en, es).

Toda mensagem voltada ao usuário sai daqui — nada de string solta no
código. Para adicionar um idioma, basta acrescentar um dicionário.
"""

DEFAULT_LANG = "pt"

MESSAGES: dict[str, dict[str, str]] = {
    "pt": {
        "help": (
            "🤖 *PixZap* — confirmação automática de Pix\n\n"
            "Comandos:\n"
            "• *cobrar 150,00 João pedido 12* — gera o Pix copia-e-cola\n"
            "• *pendentes* — cobranças aguardando pagamento\n"
            "• *hoje* — resumo do dia (pagas e total recebido)\n"
            "• *cancelar 12* — cancela a cobrança #12\n"
            "• *painel* — link seguro para ver suas métricas no navegador\n"
            "• *ajuda* — mostra esta mensagem\n\n"
            "Quando o Pix cair, eu te aviso aqui. 💸\n"
            "⚠️ Nunca entregue pedido por screenshot: espere a minha confirmação."
        ),
        "invalid_amount": ("Valor inválido. Exemplos: *cobrar 150* ou "
                           "*cobrar 89,90 Maria pedido 7*"),
        "charge_created": ("✅ Cobrança {summary} criada.\n\n"
                           "Encaminhe o código abaixo para o cliente pagar "
                           "(Pix copia-e-cola):\n\n{code}\n\n"
                           "Eu aviso aqui assim que o pagamento cair. 🔔"),
        "no_pending": "Nenhuma cobrança pendente. 🎉",
        "pending_header": "⏳ *Cobranças pendentes:*",
        "total_due": "Total a receber: {total}",
        "daily_summary": ("📊 *Resumo de {date}*\n\nPagas hoje ({count}):\n{lines}\n\n"
                          "💰 Recebido hoje: {total}\n⏳ Pendentes no total: {pending}"),
        "none_yet": "(nenhuma ainda)",
        "cancel_not_found": "Cobrança #{id} não encontrada.",
        "cancel_wrong_status": ("Cobrança #{id} está '{status}' — não dá para cancelar."),
        "canceled": "🚫 Cobrança {summary} cancelada.",
        "unknown_command": "Não entendi. 🤔 Mande *ajuda* para ver os comandos.",
        "panel_link": ("🔐 Seu painel (link válido por 24h, não compartilhe):\n{url}"),
        "panel_disabled": ("O painel web não está configurado nesta instância "
                           "(defina public_url no config.yaml)."),
        "pay_confirmed": ("✅ Pix de {amount}{payer} confirmado!\n"
                          "Cobrança {summary} está PAGA. Pode liberar o pedido. 🎉"),
        "pay_mismatch": ("⚠️ Valor divergente na cobrança {summary}: esperado "
                         "{expected}, recebido {received}. A cobrança segue "
                         "PENDENTE — confira antes de entregar."),
        "pay_unmatched": ("⚠️ Recebi um Pix de {amount}{payer} sem cobrança "
                          "associada (txid {txid}). Confira no app do banco "
                          "antes de entregar qualquer pedido."),
        "pay_wrong_status": ("⚠️ Pix de {amount} recebido para a cobrança "
                             "{summary}, que está '{status}'. Confira manualmente."),
        "payer_from": " de {name}",
        "status_pendente": "pendente",
        "status_pago": "pago",
        "status_cancelado": "cancelado",
        "panel_title": "Painel PixZap",
        "panel_received_today": "Recebido hoje",
        "panel_received_7d": "Últimos 7 dias",
        "panel_pending": "A receber (pendentes)",
        "panel_charges": "Cobranças recentes",
        "panel_payments": "Pagamentos recebidos",
        "panel_empty": "Nada por aqui ainda.",
        "panel_expired": "Link inválido ou expirado. Peça um novo mandando *painel* no WhatsApp.",
    },
    "en": {
        "help": (
            "🤖 *PixZap* — automatic Pix payment confirmation\n\n"
            "Commands:\n"
            "• *cobrar 150.00 John order 12* — creates the Pix code\n"
            "• *pendentes* — charges awaiting payment\n"
            "• *hoje* — today's summary (paid and total received)\n"
            "• *cancelar 12* — cancels charge #12\n"
            "• *painel* — secure link to your metrics dashboard\n"
            "• *ajuda* — shows this message\n\n"
            "I'll notify you here the moment the money lands. 💸\n"
            "⚠️ Never ship an order based on a screenshot: wait for my confirmation."
        ),
        "invalid_amount": "Invalid amount. Examples: *cobrar 150* or *cobrar 89,90 Mary order 7*",
        "charge_created": ("✅ Charge {summary} created.\n\n"
                           "Forward the code below to your customer "
                           "(Pix copy-and-paste):\n\n{code}\n\n"
                           "I'll let you know as soon as the payment lands. 🔔"),
        "no_pending": "No pending charges. 🎉",
        "pending_header": "⏳ *Pending charges:*",
        "total_due": "Total receivable: {total}",
        "daily_summary": ("📊 *Summary for {date}*\n\nPaid today ({count}):\n{lines}\n\n"
                          "💰 Received today: {total}\n⏳ Total pending: {pending}"),
        "none_yet": "(none yet)",
        "cancel_not_found": "Charge #{id} not found.",
        "cancel_wrong_status": "Charge #{id} is '{status}' — it can't be canceled.",
        "canceled": "🚫 Charge {summary} canceled.",
        "unknown_command": "I didn't get that. 🤔 Send *ajuda* to see the commands.",
        "panel_link": "🔐 Your dashboard (link valid for 24h, do not share):\n{url}",
        "panel_disabled": "The web dashboard is not configured on this instance (set public_url in config.yaml).",
        "pay_confirmed": ("✅ Pix of {amount}{payer} confirmed!\n"
                          "Charge {summary} is PAID. You can release the order. 🎉"),
        "pay_mismatch": ("⚠️ Amount mismatch on charge {summary}: expected {expected}, "
                         "received {received}. The charge remains PENDING — check before shipping."),
        "pay_unmatched": ("⚠️ Received a Pix of {amount}{payer} with no matching charge "
                          "(txid {txid}). Check your bank app before shipping anything."),
        "pay_wrong_status": ("⚠️ Pix of {amount} received for charge {summary}, "
                             "which is '{status}'. Please check manually."),
        "payer_from": " from {name}",
        "status_pendente": "pending",
        "status_pago": "paid",
        "status_cancelado": "canceled",
        "panel_title": "PixZap Dashboard",
        "panel_received_today": "Received today",
        "panel_received_7d": "Last 7 days",
        "panel_pending": "Receivable (pending)",
        "panel_charges": "Recent charges",
        "panel_payments": "Payments received",
        "panel_empty": "Nothing here yet.",
        "panel_expired": "Invalid or expired link. Ask for a new one by sending *painel* on WhatsApp.",
    },
    "es": {
        "help": (
            "🤖 *PixZap* — confirmación automática de Pix\n\n"
            "Comandos:\n"
            "• *cobrar 150,00 Juan pedido 12* — genera el código Pix\n"
            "• *pendentes* — cobros esperando pago\n"
            "• *hoje* — resumen del día (pagados y total recibido)\n"
            "• *cancelar 12* — cancela el cobro #12\n"
            "• *painel* — enlace seguro a tu panel de métricas\n"
            "• *ajuda* — muestra este mensaje\n\n"
            "Cuando caiga el Pix, te aviso aquí. 💸\n"
            "⚠️ Nunca entregues un pedido por captura de pantalla: espera mi confirmación."
        ),
        "invalid_amount": "Valor inválido. Ejemplos: *cobrar 150* o *cobrar 89,90 María pedido 7*",
        "charge_created": ("✅ Cobro {summary} creado.\n\n"
                           "Reenvía el código de abajo a tu cliente "
                           "(Pix copia-y-pega):\n\n{code}\n\n"
                           "Te aviso en cuanto caiga el pago. 🔔"),
        "no_pending": "Ningún cobro pendiente. 🎉",
        "pending_header": "⏳ *Cobros pendientes:*",
        "total_due": "Total por recibir: {total}",
        "daily_summary": ("📊 *Resumen de {date}*\n\nPagados hoy ({count}):\n{lines}\n\n"
                          "💰 Recibido hoy: {total}\n⏳ Pendientes en total: {pending}"),
        "none_yet": "(ninguno aún)",
        "cancel_not_found": "Cobro #{id} no encontrado.",
        "cancel_wrong_status": "El cobro #{id} está '{status}' — no se puede cancelar.",
        "canceled": "🚫 Cobro {summary} cancelado.",
        "unknown_command": "No entendí. 🤔 Envía *ajuda* para ver los comandos.",
        "panel_link": "🔐 Tu panel (enlace válido por 24h, no lo compartas):\n{url}",
        "panel_disabled": "El panel web no está configurado en esta instancia (define public_url en config.yaml).",
        "pay_confirmed": ("✅ ¡Pix de {amount}{payer} confirmado!\n"
                          "El cobro {summary} está PAGADO. Puedes liberar el pedido. 🎉"),
        "pay_mismatch": ("⚠️ Valor divergente en el cobro {summary}: esperado {expected}, "
                         "recibido {received}. El cobro sigue PENDIENTE — verifica antes de entregar."),
        "pay_unmatched": ("⚠️ Recibí un Pix de {amount}{payer} sin cobro asociado "
                          "(txid {txid}). Verifica en tu banco antes de entregar."),
        "pay_wrong_status": ("⚠️ Pix de {amount} recibido para el cobro {summary}, "
                             "que está '{status}'. Verifica manualmente."),
        "payer_from": " de {name}",
        "status_pendente": "pendiente",
        "status_pago": "pagado",
        "status_cancelado": "cancelado",
        "panel_title": "Panel PixZap",
        "panel_received_today": "Recibido hoy",
        "panel_received_7d": "Últimos 7 días",
        "panel_pending": "Por recibir (pendientes)",
        "panel_charges": "Cobros recientes",
        "panel_payments": "Pagos recibidos",
        "panel_empty": "Nada por aquí todavía.",
        "panel_expired": "Enlace inválido o expirado. Pide uno nuevo enviando *painel* por WhatsApp.",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Busca a mensagem no idioma pedido, com fallback para o pt-BR."""
    catalog = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    template = catalog.get(key) or MESSAGES[DEFAULT_LANG][key]
    return template.format(**kwargs) if kwargs else template


def status_label(lang: str, status_value: str) -> str:
    """Traduz o valor interno do status (sempre pt) para exibição."""
    return t(lang, f"status_{status_value}")
