"""Catálogo de mensagens multilíngue.

Idiomas e mercados-alvo (ver docs/aderencia-mercados.md):
- pt — Brasil (Pix): mercado nº 1, o produto fala "Pix".
- en — Índia (UPI), Nigéria e Quênia (transferência bancária): fala
  "payment/transfer", sem citar Pix, que não existe lá.
- es — México (SPEI), Argentina e Colômbia: fala "pago/transferencia".
- id — Indonésia (QRIS/transfer): "bukti transfer palsu" é praga nacional.

Toda mensagem voltada ao usuário sai daqui — nada de string solta no
código. Para adicionar um idioma, basta acrescentar um dicionário com as
MESMAS chaves (o teste test_all_languages_have_all_keys garante).
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
            "• *saldo* — saldo disponível na sua conta\n"
            "• *transferir 200 pro pix: chave@email.com* — envia um Pix\n"
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
        "cancel_wrong_status": "Cobrança #{id} está '{status}', não dá para cancelar.",
        "canceled": "🚫 Cobrança {summary} cancelada.",
        "unknown_command": "Não entendi. 🤔 Mande *ajuda* para ver os comandos.",
        "panel_link": "🔐 Seu painel (link válido por 24h, não compartilhe):\n{url}",
        "panel_disabled": ("O painel web não está configurado nesta instância "
                           "(defina public_url no config.yaml)."),
        "pay_confirmed": ("✅ Pix de {amount}{payer} confirmado!\n"
                          "Cobrança {summary} está PAGA. Pode liberar o pedido. 🎉"),
        "pay_mismatch": ("⚠️ Valor divergente na cobrança {summary}: esperado "
                         "{expected}, recebido {received}. A cobrança segue "
                         "PENDENTE, confira antes de entregar."),
        "pay_unmatched": ("⚠️ Recebi um Pix de {amount}{payer} sem cobrança "
                          "associada (txid {txid}). Confira no app do banco "
                          "antes de entregar qualquer pedido."),
        "pay_wrong_status": ("⚠️ Pix de {amount} recebido para a cobrança "
                             "{summary}, que está '{status}'. Confira manualmente."),
        "payer_from": " de {name}",
        "balance": "💰 Saldo disponível: {amount}",
        "transfer_disabled": ("Transferências pelo chat estão desativadas. Para "
                              "ativar, defina transfer_daily_limit no config.yaml."),
        "transfer_unsupported": ("O provedor '{provider}' ainda não suporta "
                                 "saldo/transferência pelo PixZap."),
        "transfer_invalid": ("Não entendi. Use: *transferir 200 pro pix: "
                             "chave@email.com*"),
        "transfer_limit": ("🚫 Limite diário de transferências atingido: {limit} "
                           "(hoje já foram {used}). Amanhã libera de novo."),
        "transfer_confirm": ("⚠️ *Confirme a transferência:*\n{amount} para o Pix "
                             "*{key}*.\n\nSe estiver certo, responda *confirmar "
                             "{code}* em até 5 minutos."),
        "transfer_done": ("✅ Transferência de {amount} para {key} enviada "
                          "(protocolo {ref})."),
        "transfer_failed": "❌ A transferência não foi executada: {reason}",
        "confirm_invalid": ("Código inválido ou expirado. Comece de novo com "
                            "*transferir valor pix chave*."),
        "pay_extra": ("🚨 ATENÇÃO: recebi um SEGUNDO pagamento de {amount}{payer} "
                      "para a cobrança {summary}, que JÁ ESTAVA PAGA. Provável "
                      "pagamento em duplicidade (código reaproveitado ou pessoa "
                      "errada pagou junto) — combine a devolução com quem pagou."),
        "cancel_usage": "Para cancelar, mande *cancelar* e o número da cobrança. Ex.: *cancelar 12*",
        "non_text": ("Não consigo ler áudio, imagem ou documento. 🙈 E lembre-se: "
                     "print não é comprovante — quando o Pix cair de verdade, eu "
                     "aviso aqui sozinho. Mande *ajuda* para ver os comandos."),
        "charge_error": ("❌ Não consegui gerar a cobrança agora (problema no "
                         "provedor de pagamento). Tente de novo em instantes."),
        "psp_error": ("❌ Não consegui falar com o provedor de pagamento agora. "
                      "Tente de novo em instantes."),
        "charge_dup_warning": ("⚠️ Já existe uma cobrança IGUAL pendente: {summary}. "
                               "Se foi duplo toque, mande *cancelar {id}*."),
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
    # en: Índia/Nigéria/Quênia — o trilho é UPI ou transferência bancária,
    # então as mensagens falam "payment/transfer", nunca "Pix".
    "en": {
        "help": (
            "🤖 *PixZap* — automatic payment confirmation\n\n"
            "Commands:\n"
            "• *cobrar 150.00 John order 12* — creates a payment request\n"
            "• *pendentes* — charges awaiting payment\n"
            "• *hoje* — today's summary (paid and total received)\n"
            "• *saldo* — available account balance\n"
            "• *transferir 200 to key@email.com* — sends a transfer\n"
            "• *cancelar 12* — cancels charge #12\n"
            "• *painel* — secure link to your metrics dashboard\n"
            "• *ajuda* — shows this message\n\n"
            "I'll notify you here the moment the money lands. 💸\n"
            "⚠️ Never ship an order based on a screenshot: wait for my confirmation."
        ),
        "invalid_amount": "Invalid amount. Examples: *cobrar 150* or *cobrar 89.90 Mary order 7*",
        "charge_created": ("✅ Charge {summary} created.\n\n"
                           "Forward the payment code below to your customer:"
                           "\n\n{code}\n\n"
                           "I'll let you know as soon as the payment lands. 🔔"),
        "no_pending": "No pending charges. 🎉",
        "pending_header": "⏳ *Pending charges:*",
        "total_due": "Total receivable: {total}",
        "daily_summary": ("📊 *Summary for {date}*\n\nPaid today ({count}):\n{lines}\n\n"
                          "💰 Received today: {total}\n⏳ Total pending: {pending}"),
        "none_yet": "(none yet)",
        "cancel_not_found": "Charge #{id} not found.",
        "cancel_wrong_status": "Charge #{id} is '{status}', it can't be canceled.",
        "canceled": "🚫 Charge {summary} canceled.",
        "unknown_command": "I didn't get that. 🤔 Send *ajuda* to see the commands.",
        "panel_link": "🔐 Your dashboard (link valid for 24h, do not share):\n{url}",
        "panel_disabled": "The web dashboard is not configured on this instance (set public_url in config.yaml).",
        "pay_confirmed": ("✅ Payment of {amount}{payer} confirmed!\n"
                          "Charge {summary} is PAID. You can release the order. 🎉"),
        "pay_mismatch": ("⚠️ Amount mismatch on charge {summary}: expected {expected}, "
                         "received {received}. The charge remains PENDING, check before shipping."),
        "pay_unmatched": ("⚠️ Received a payment of {amount}{payer} with no matching charge "
                          "(txid {txid}). Check your bank app before shipping anything."),
        "pay_wrong_status": ("⚠️ Payment of {amount} received for charge {summary}, "
                             "which is '{status}'. Please check manually."),
        "payer_from": " from {name}",
        "balance": "💰 Available balance: {amount}",
        "transfer_disabled": ("Chat transfers are disabled. To enable them, set "
                              "transfer_daily_limit in config.yaml."),
        "transfer_unsupported": "Provider '{provider}' does not support balance/transfers via PixZap yet.",
        "transfer_invalid": "I didn't get that. Use: *transferir 200 to key@email.com*",
        "transfer_limit": ("🚫 Daily transfer limit reached: {limit} "
                           "(already sent today: {used}). Resets tomorrow."),
        "transfer_confirm": ("⚠️ *Confirm the transfer:*\n{amount} to *{key}*.\n\n"
                             "If that's right, reply *confirmar {code}* within 5 minutes."),
        "transfer_done": "✅ Transfer of {amount} to {key} sent (reference {ref}).",
        "transfer_failed": "❌ The transfer was not executed: {reason}",
        "confirm_invalid": "Invalid or expired code. Start again with *transferir amount key*.",
        "pay_extra": ("🚨 ATTENTION: I received a SECOND payment of {amount}{payer} "
                      "for charge {summary}, which was ALREADY PAID. Likely a duplicate "
                      "payment (reused code or the wrong person also paid) — arrange a "
                      "refund with the payer."),
        "cancel_usage": "To cancel, send *cancelar* plus the charge number. E.g.: *cancelar 12*",
        "non_text": ("I can't read audio, images or documents. 🙈 And remember: a "
                     "screenshot is not proof — when the money truly lands, I'll tell "
                     "you here myself. Send *ajuda* to see the commands."),
        "charge_error": ("❌ I couldn't create the charge right now (payment "
                         "provider issue). Please try again in a moment."),
        "psp_error": ("❌ I couldn't reach the payment provider right now. "
                      "Please try again in a moment."),
        "charge_dup_warning": ("⚠️ An IDENTICAL charge is already pending: {summary}. "
                               "If that was a double tap, send *cancelar {id}*."),
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
    # es: México (SPEI), Argentina, Colômbia — fala "pago/transferencia".
    "es": {
        "help": (
            "🤖 *PixZap* — confirmación automática de pagos\n\n"
            "Comandos:\n"
            "• *cobrar 150,00 Juan pedido 12* — genera el cobro\n"
            "• *pendentes* — cobros esperando pago\n"
            "• *hoje* — resumen del día (pagados y total recibido)\n"
            "• *saldo* — saldo disponible en tu cuenta\n"
            "• *transferir 200 a clave@email.com* — envía una transferencia\n"
            "• *cancelar 12* — cancela el cobro #12\n"
            "• *painel* — enlace seguro a tu panel de métricas\n"
            "• *ajuda* — muestra este mensaje\n\n"
            "Cuando caiga el pago, te aviso aquí. 💸\n"
            "⚠️ Nunca entregues un pedido por captura de pantalla: espera mi confirmación."
        ),
        "invalid_amount": "Valor inválido. Ejemplos: *cobrar 150* o *cobrar 89,90 María pedido 7*",
        "charge_created": ("✅ Cobro {summary} creado.\n\n"
                           "Reenvía el código de pago a tu cliente:\n\n{code}\n\n"
                           "Te aviso en cuanto caiga el pago. 🔔"),
        "no_pending": "Ningún cobro pendiente. 🎉",
        "pending_header": "⏳ *Cobros pendientes:*",
        "total_due": "Total por recibir: {total}",
        "daily_summary": ("📊 *Resumen de {date}*\n\nPagados hoy ({count}):\n{lines}\n\n"
                          "💰 Recibido hoy: {total}\n⏳ Pendientes en total: {pending}"),
        "none_yet": "(ninguno aún)",
        "cancel_not_found": "Cobro #{id} no encontrado.",
        "cancel_wrong_status": "El cobro #{id} está '{status}', no se puede cancelar.",
        "canceled": "🚫 Cobro {summary} cancelado.",
        "unknown_command": "No entendí. 🤔 Envía *ajuda* para ver los comandos.",
        "panel_link": "🔐 Tu panel (enlace válido por 24h, no lo compartas):\n{url}",
        "panel_disabled": "El panel web no está configurado en esta instancia (define public_url en config.yaml).",
        "pay_confirmed": ("✅ ¡Pago de {amount}{payer} confirmado!\n"
                          "El cobro {summary} está PAGADO. Puedes liberar el pedido. 🎉"),
        "pay_mismatch": ("⚠️ Valor divergente en el cobro {summary}: esperado {expected}, "
                         "recibido {received}. El cobro sigue PENDIENTE, verifica antes de entregar."),
        "pay_unmatched": ("⚠️ Recibí un pago de {amount}{payer} sin cobro asociado "
                          "(txid {txid}). Verifica en tu banco antes de entregar."),
        "pay_wrong_status": ("⚠️ Pago de {amount} recibido para el cobro {summary}, "
                             "que está '{status}'. Verifica manualmente."),
        "payer_from": " de {name}",
        "balance": "💰 Saldo disponible: {amount}",
        "transfer_disabled": ("Las transferencias por chat están desactivadas. Para "
                              "activarlas, define transfer_daily_limit en config.yaml."),
        "transfer_unsupported": "El proveedor '{provider}' aún no soporta saldo/transferencias vía PixZap.",
        "transfer_invalid": "No entendí. Usa: *transferir 200 a clave@email.com*",
        "transfer_limit": ("🚫 Límite diario de transferencias alcanzado: {limit} "
                           "(hoy ya enviaste {used}). Se reinicia mañana."),
        "transfer_confirm": ("⚠️ *Confirma la transferencia:*\n{amount} para *{key}*.\n\n"
                             "Si está bien, responde *confirmar {code}* en 5 minutos."),
        "transfer_done": "✅ Transferencia de {amount} a {key} enviada (referencia {ref}).",
        "transfer_failed": "❌ La transferencia no se ejecutó: {reason}",
        "confirm_invalid": "Código inválido o expirado. Empieza de nuevo con *transferir valor clave*.",
        "pay_extra": ("🚨 ATENCIÓN: recibí un SEGUNDO pago de {amount}{payer} para el "
                      "cobro {summary}, que YA ESTABA PAGADO. Probable pago duplicado "
                      "(código reutilizado o la persona equivocada también pagó) — "
                      "acuerda la devolución con quien pagó."),
        "cancel_usage": "Para cancelar, envía *cancelar* y el número del cobro. Ej.: *cancelar 12*",
        "non_text": ("No puedo leer audios, imágenes ni documentos. 🙈 Y recuerda: una "
                     "captura no es comprobante — cuando el dinero caiga de verdad, te "
                     "aviso yo mismo. Envía *ajuda* para ver los comandos."),
        "charge_error": ("❌ No pude generar el cobro ahora (problema con el "
                         "proveedor de pagos). Intenta de nuevo en un momento."),
        "psp_error": ("❌ No pude comunicarme con el proveedor de pagos ahora. "
                      "Intenta de nuevo en un momento."),
        "charge_dup_warning": ("⚠️ Ya existe un cobro IDÉNTICO pendiente: {summary}. "
                               "Si fue un doble toque, envía *cancelar {id}*."),
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
    # id: Indonésia — "bukti transfer palsu" (comprovante falso) é epidemia
    # documentada pelo Bank Indonesia; trilho: transferência bancária/QRIS.
    "id": {
        "help": (
            "🤖 *PixZap* — konfirmasi pembayaran otomatis\n\n"
            "Perintah:\n"
            "• *cobrar 150.000 Budi pesanan 12* — membuat tagihan\n"
            "• *pendentes* — tagihan yang menunggu pembayaran\n"
            "• *hoje* — ringkasan hari ini (lunas dan total diterima)\n"
            "• *saldo* — saldo yang tersedia di akun Anda\n"
            "• *transferir 200.000 ke kunci@email.com* — kirim transfer\n"
            "• *cancelar 12* — membatalkan tagihan #12\n"
            "• *painel* — tautan aman ke dasbor metrik Anda\n"
            "• *ajuda* — menampilkan pesan ini\n\n"
            "Begitu uang masuk, saya kabari di sini. 💸\n"
            "⚠️ Jangan pernah kirim pesanan karena screenshot: tunggu konfirmasi saya."
        ),
        "invalid_amount": "Nilai tidak valid. Contoh: *cobrar 150000* atau *cobrar 89.900 Budi pesanan 7*",
        "charge_created": ("✅ Tagihan {summary} dibuat.\n\n"
                           "Teruskan kode pembayaran di bawah ke pelanggan Anda:"
                           "\n\n{code}\n\n"
                           "Saya kabari begitu pembayarannya masuk. 🔔"),
        "no_pending": "Tidak ada tagihan tertunda. 🎉",
        "pending_header": "⏳ *Tagihan tertunda:*",
        "total_due": "Total piutang: {total}",
        "daily_summary": ("📊 *Ringkasan {date}*\n\nLunas hari ini ({count}):\n{lines}\n\n"
                          "💰 Diterima hari ini: {total}\n⏳ Total tertunda: {pending}"),
        "none_yet": "(belum ada)",
        "cancel_not_found": "Tagihan #{id} tidak ditemukan.",
        "cancel_wrong_status": "Tagihan #{id} berstatus '{status}', tidak bisa dibatalkan.",
        "canceled": "🚫 Tagihan {summary} dibatalkan.",
        "unknown_command": "Saya tidak mengerti. 🤔 Kirim *ajuda* untuk melihat perintah.",
        "panel_link": "🔐 Dasbor Anda (tautan berlaku 24 jam, jangan dibagikan):\n{url}",
        "panel_disabled": "Dasbor web belum dikonfigurasi di instans ini (atur public_url di config.yaml).",
        "pay_confirmed": ("✅ Pembayaran {amount}{payer} terkonfirmasi!\n"
                          "Tagihan {summary} sudah LUNAS. Pesanan boleh dikirim. 🎉"),
        "pay_mismatch": ("⚠️ Nilai tidak cocok pada tagihan {summary}: seharusnya {expected}, "
                         "diterima {received}. Tagihan tetap TERTUNDA, periksa sebelum mengirim."),
        "pay_unmatched": ("⚠️ Menerima pembayaran {amount}{payer} tanpa tagihan terkait "
                          "(txid {txid}). Periksa aplikasi bank Anda sebelum mengirim apa pun."),
        "pay_wrong_status": ("⚠️ Pembayaran {amount} diterima untuk tagihan {summary}, "
                             "yang berstatus '{status}'. Periksa secara manual."),
        "payer_from": " dari {name}",
        "balance": "💰 Saldo tersedia: {amount}",
        "transfer_disabled": ("Transfer via chat dinonaktifkan. Untuk mengaktifkan, "
                              "atur transfer_daily_limit di config.yaml."),
        "transfer_unsupported": "Penyedia '{provider}' belum mendukung saldo/transfer via PixZap.",
        "transfer_invalid": "Saya tidak mengerti. Gunakan: *transferir 200000 ke kunci@email.com*",
        "transfer_limit": ("🚫 Batas transfer harian tercapai: {limit} "
                           "(hari ini sudah {used}). Reset besok."),
        "transfer_confirm": ("⚠️ *Konfirmasi transfer:*\n{amount} ke *{key}*.\n\n"
                             "Jika benar, balas *confirmar {code}* dalam 5 menit."),
        "transfer_done": "✅ Transfer {amount} ke {key} terkirim (referensi {ref}).",
        "transfer_failed": "❌ Transfer tidak dijalankan: {reason}",
        "confirm_invalid": "Kode tidak valid atau kedaluwarsa. Mulai lagi dengan *transferir nilai kunci*.",
        "pay_extra": ("🚨 PERHATIAN: saya menerima pembayaran KEDUA sebesar {amount}{payer} "
                      "untuk tagihan {summary}, yang SUDAH LUNAS. Kemungkinan pembayaran "
                      "ganda (kode dipakai ulang atau orang yang salah ikut membayar) — "
                      "atur pengembalian dengan pembayarnya."),
        "cancel_usage": "Untuk membatalkan, kirim *cancelar* dan nomor tagihan. Contoh: *cancelar 12*",
        "non_text": ("Saya tidak bisa membaca audio, gambar, atau dokumen. 🙈 Ingat: "
                     "screenshot bukan bukti bayar — begitu uang benar-benar masuk, saya "
                     "sendiri yang mengabari. Kirim *ajuda* untuk melihat perintah."),
        "charge_error": ("❌ Saya tidak bisa membuat tagihan sekarang (masalah di "
                         "penyedia pembayaran). Coba lagi sebentar lagi."),
        "psp_error": ("❌ Saya tidak bisa menghubungi penyedia pembayaran sekarang. "
                      "Coba lagi sebentar lagi."),
        "charge_dup_warning": ("⚠️ Sudah ada tagihan yang SAMA PERSIS tertunda: {summary}. "
                               "Kalau itu ketukan ganda, kirim *cancelar {id}*."),
        "status_pendente": "tertunda",
        "status_pago": "lunas",
        "status_cancelado": "dibatalkan",
        "panel_title": "Dasbor PixZap",
        "panel_received_today": "Diterima hari ini",
        "panel_received_7d": "7 hari terakhir",
        "panel_pending": "Piutang (tertunda)",
        "panel_charges": "Tagihan terbaru",
        "panel_payments": "Pembayaran diterima",
        "panel_empty": "Belum ada apa-apa di sini.",
        "panel_expired": "Tautan tidak valid atau kedaluwarsa. Minta yang baru dengan mengirim *painel* di WhatsApp.",
    },
}


def t(lang: str, message_key: str, **kwargs) -> str:
    """Busca a mensagem no idioma pedido, com fallback para o pt-BR.

    O parâmetro se chama message_key (e não key) porque as mensagens de
    transferência usam {key} como placeholder da chave Pix.
    """
    catalog = MESSAGES.get(lang, MESSAGES[DEFAULT_LANG])
    template = catalog.get(message_key) or MESSAGES[DEFAULT_LANG][message_key]
    return template.format(**kwargs) if kwargs else template


def status_label(lang: str, status_value: str) -> str:
    """Traduz o valor interno do status (sempre pt) para exibição."""
    return t(lang, f"status_{status_value}")
