"""Servidor de webhooks: recebe mensagens do WhatsApp e eventos do PSP."""

import hmac
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse

from . import __version__
from .auth import verify_token as verify_magic_token
from .bot import Bot
from .matching import Reconciler
from .panel import render_admin_panel, render_expired, render_seller_panel
from .psp.base import PspClient
from .whatsapp.base import WhatsAppClient

log = logging.getLogger("pixzap.server")


def create_app(bot: Bot, reconciler: Reconciler, psp: PspClient,
               wa_client: WhatsAppClient, verify_token: str = "",
               dashboard_secret: str = "", admin_token: str = "",
               lang: str = "pt", tz_name: str = "America/Sao_Paulo") -> FastAPI:
    app = FastAPI(title="PixZap", version=__version__)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    # ── painéis web ─────────────────────────────────────────────────
    @app.get("/painel", response_class=HTMLResponse)
    def seller_panel(token: str = ""):
        """Métricas do vendedor — acesso por link mágico gerado no chat."""
        subject = verify_magic_token(dashboard_secret, token) if dashboard_secret else None
        if subject is None or subject not in bot.seller_numbers:
            return HTMLResponse(render_expired(lang), status_code=403)
        return render_seller_panel(bot.storage, lang, tz_name)

    @app.get("/admin", response_class=HTMLResponse)
    def admin_panel(token: str = ""):
        """Registros completos — exige PIXZAP_ADMIN_TOKEN."""
        if not admin_token or not hmac.compare_digest(token, admin_token):
            return HTMLResponse("acesso negado", status_code=403)
        return render_admin_panel(bot.storage)

    # ── WhatsApp ────────────────────────────────────────────────────
    @app.get("/webhook/whatsapp")
    def whatsapp_verify(request: Request):
        """Handshake de verificação da Cloud API (Meta)."""
        params = request.query_params
        if (params.get("hub.mode") == "subscribe"
                and params.get("hub.verify_token") == verify_token):
            return Response(content=params.get("hub.challenge", ""),
                            media_type="text/plain")
        return Response(status_code=403)

    @app.post("/webhook/whatsapp")
    async def whatsapp_incoming(request: Request):
        # Sempre responder 200 à Meta: erro nosso não pode virar retry em
        # loop (retries reprocessariam comandos, ex.: cobrança duplicada).
        try:
            payload = await request.json()
        except Exception:
            log.warning("Webhook do WhatsApp com corpo inválido — ignorado")
            return {"status": "ignorado"}
        for message in wa_client.parse_incoming(payload):
            try:
                reply = bot.handle(message.sender, message.text)
                if reply:
                    wa_client.send_text(message.sender, reply)
            except Exception:
                log.exception("Erro ao processar mensagem de %s", message.sender)
        return {"status": "ok"}

    # ── PSP (pagamentos) ────────────────────────────────────────────
    @app.post("/webhook/psp")
    async def psp_webhook(request: Request):
        body = await request.body()
        headers = dict(request.headers)
        # O Mercado Pago manda o id na query string; o adaptador precisa
        # dele para validar a assinatura.
        if "data.id" in request.query_params:
            headers["x-data-id"] = request.query_params["data.id"]

        if not psp.verify_webhook(headers, body):
            log.warning("Webhook de PSP rejeitado: autenticação inválida")
            return Response(status_code=401)

        try:
            payload = await request.json()
        except Exception:
            return Response(status_code=400)
        event = psp.parse_webhook(payload)
        if event is None:
            return {"status": "ignorado"}  # evento que não confirma dinheiro

        result = reconciler.handle_payment(event, raw=payload)
        log.info("Pagamento %s → %s", event.txid, result.outcome.value)
        if result.seller_message:
            try:
                bot.notify_sellers(wa_client, result.seller_message)
            except Exception:
                # A conciliação já foi persistida; falha de envio não pode
                # derrubar o webhook (o PSP faria retry e cairia no DUPLICATE).
                log.exception("Falha ao notificar vendedores")
        return {"status": result.outcome.value}

    return app
