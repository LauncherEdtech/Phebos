"""Comandos do vendedor no chat — a interface do produto é o próprio WhatsApp.

Segurança (nunca enfraquecer): só números da lista `seller_numbers` podem
dar comandos. Mensagem de qualquer outro número é ignorada em silêncio.

Os comandos são os mesmos em todos os idiomas (cobrar/pendentes/hoje/...);
o que muda com o `language` do config são as RESPOSTAS (ver i18n.py).
"""

import re
import secrets
import time
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .auth import make_token
from .i18n import DEFAULT_LANG, status_label, t
from .models import Charge, format_money, parse_brl
from .psp.base import PspClient
from .storage import Storage

CONFIRM_TTL_SECONDS = 300  # transferência pendente expira em 5 min

# Captura qualquer token como valor; a validação de verdade é do parse_brl,
# para que "cobrar abc" responda "valor inválido" em vez de "não entendi".
# re.S: descrição pode vir em várias linhas (gente cola o pedido inteiro).
COBRAR_RE = re.compile(
    r"^cobrar\s+(?P<valor>r\$\s*\S+|\S+)(?:\s+(?P<descricao>.+))?$",
    re.IGNORECASE | re.S,
)
CANCELAR_RE = re.compile(r"^cancelar\s+#?(?P<id>\d+)$", re.IGNORECASE)
# aceita "transferir 200 pro pix: xxx", "transferir 200 para xxx",
# "transferir 200,50 pix xxx" e "transferir 200 xxx"
TRANSFERIR_RE = re.compile(r"^transferir\s+(?P<valor>r\$\s*\S+|\S+)\s+(?P<resto>.+)$",
                           re.IGNORECASE | re.S)

MAX_DESCRIPTION_LEN = 120  # descrição maior é cortada (mensagens legíveis)
_KEY_FILLER_RE = re.compile(r"^(?:(?:pro|para|pra|to|a|al)\s+)?(?:pix\s*[: ]\s*|pix\s+)?",
                            re.IGNORECASE)
CONFIRMAR_RE = re.compile(r"^confirmar\s+(?P<codigo>\d{6})$", re.IGNORECASE)


class Bot:
    def __init__(self, storage: Storage, psp: PspClient,
                 seller_numbers: list[str], tz_name: str = "America/Sao_Paulo",
                 lang: str = DEFAULT_LANG, public_url: str = "",
                 dashboard_secret: str = "",
                 transfer_daily_limit_cents: int = 0):
        self.storage = storage
        self.psp = psp
        self.seller_numbers = set(seller_numbers)
        self.tz = ZoneInfo(tz_name)
        self.lang = lang
        self.public_url = public_url.rstrip("/")
        self.dashboard_secret = dashboard_secret
        # 0 = transferências desativadas (padrão seguro: opt-in no config)
        self.transfer_daily_limit_cents = transfer_daily_limit_cents
        # transferências aguardando código: sender → (code, amount, key, expira_em)
        self._pending_transfers: dict[str, tuple[str, int, str, float]] = {}

    def handle(self, sender: str, text: str) -> Optional[str]:
        """Processa uma mensagem e devolve a resposta (None = ignorar)."""
        if sender not in self.seller_numbers:
            return None  # regra de segurança: desconhecido não conversa com o bot

        text = text.strip()
        # "ajuda!", "Pendentes." etc.: pontuação no fim não muda a intenção
        lowered = text.lower().rstrip("!?.,;: ")

        if lowered in ("ajuda", "help", "menu", "oi", "olá", "ola", "hola",
                       "hi", "hello", "comandos", "início", "inicio", "start"):
            return t(self.lang, "help")

        match = COBRAR_RE.match(text)
        if match:
            return self._create_charge(match.group("valor"),
                                       (match.group("descricao") or "").strip())

        if lowered in ("pendentes", "pendente", "pendencias", "pendências"):
            return self._list_pending()

        if lowered in ("hoje", "resumo", "vendas"):
            return self._daily_summary()

        if lowered in ("painel", "panel", "dashboard", "métricas", "metricas"):
            return self._panel_link(sender)

        if lowered in ("saldo", "balance"):
            return self._balance()

        match = TRANSFERIR_RE.match(text)
        if match:
            return self._request_transfer(sender, match.group("valor"),
                                          match.group("resto").strip())

        match = CONFIRMAR_RE.match(text)
        if match:
            return self._confirm_transfer(sender, match.group("codigo"))

        match = CANCELAR_RE.match(text)
        if match:
            return self._cancel(int(match.group("id")))

        # Comando reconhecido mas malformado → ensina o uso certo em vez
        # do genérico "não entendi" (simulação de usuários mostrou que
        # "cobrar" sozinho é o erro mais comum de quem está começando).
        if lowered.startswith("cobrar"):
            return t(self.lang, "invalid_amount")
        if lowered.startswith("transferir"):
            return t(self.lang, "transfer_invalid")
        if lowered.startswith("confirmar"):
            return t(self.lang, "confirm_invalid")
        if lowered.startswith("cancelar"):
            return t(self.lang, "cancel_usage")

        return t(self.lang, "unknown_command")

    def non_text_reply(self, sender: str) -> Optional[str]:
        """Resposta educada a áudio/imagem/documento de um vendedor.

        O caso clássico: vendedor encaminha o screenshot do comprovante
        para o bot esperando confirmação — precisamos reforçar que print
        não confirma nada. Desconhecidos seguem sem resposta.
        """
        if sender not in self.seller_numbers:
            return None
        return t(self.lang, "non_text")

    # ── comandos ────────────────────────────────────────────────────
    def _create_charge(self, raw_amount: str, description: str) -> str:
        amount_cents = parse_brl(raw_amount)
        if amount_cents is None:
            return t(self.lang, "invalid_amount")
        description = " ".join(description.split())[:MAX_DESCRIPTION_LEN]

        # Duplo toque no WhatsApp cria cobrança em dobro sem querer —
        # criamos mesmo assim (pode ser venda repetida de verdade), mas
        # avisamos para o vendedor cancelar uma das duas se foi engano.
        duplicate = next(
            (c for c in self.storage.pending_charges()
             if c.amount_cents == amount_cents and c.description == description),
            None)

        try:
            pix = self.psp.create_charge(amount_cents, description)
        except Exception:  # PSP fora do ar não pode virar silêncio
            return t(self.lang, "charge_error")
        charge = self.storage.save_charge(Charge(
            id=None, txid=pix.txid, amount_cents=amount_cents,
            description=description, copy_paste_code=pix.copy_paste_code,
            provider=self.psp.name,
        ))
        reply = t(self.lang, "charge_created", summary=charge.summary(),
                  code=charge.copy_paste_code)
        if duplicate is not None:
            reply += "\n\n" + t(self.lang, "charge_dup_warning",
                                summary=duplicate.summary(), id=duplicate.id)
        return reply

    def _list_pending(self) -> str:
        pending = self.storage.pending_charges()
        if not pending:
            return t(self.lang, "no_pending")
        lines = "\n".join(c.summary() for c in pending)
        total = sum(c.amount_cents for c in pending)
        return (t(self.lang, "pending_header") + "\n" + lines + "\n\n" +
                t(self.lang, "total_due", total=format_money(total)))

    def _daily_summary(self) -> str:
        now_local = datetime.now(self.tz)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_utc = start_local.astimezone(timezone.utc).isoformat(timespec="seconds")
        paid = self.storage.paid_charges_since(start_utc)
        pending = self.storage.pending_charges()
        total = sum(c.amount_cents for c in paid)
        lines = "\n".join(c.summary() for c in paid) or t(self.lang, "none_yet")
        return t(self.lang, "daily_summary",
                 date=now_local.strftime("%d/%m/%Y"), count=len(paid),
                 lines=lines, total=format_money(total), pending=len(pending))

    def _panel_link(self, sender: str) -> str:
        if not (self.public_url and self.dashboard_secret):
            return t(self.lang, "panel_disabled")
        token = make_token(self.dashboard_secret, sender)
        return t(self.lang, "panel_link",
                 url=f"{self.public_url}/painel?token={token}")

    # ── saldo e transferências ──────────────────────────────────────
    def _balance(self) -> str:
        try:
            balance = self.psp.get_balance()
        except NotImplementedError:
            return t(self.lang, "transfer_unsupported", provider=self.psp.name)
        except Exception:  # PSP fora do ar não pode virar silêncio
            return t(self.lang, "psp_error")
        return t(self.lang, "balance", amount=format_money(balance))

    def _day_start_utc(self) -> str:
        now_local = datetime.now(self.tz)
        start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(timezone.utc).isoformat(timespec="seconds")

    def _request_transfer(self, sender: str, raw_amount: str, rest: str) -> str:
        if not self.transfer_daily_limit_cents:
            return t(self.lang, "transfer_disabled")
        if not self.psp.supports_transfers:
            return t(self.lang, "transfer_unsupported", provider=self.psp.name)
        amount_cents = parse_brl(raw_amount)
        pix_key = _KEY_FILLER_RE.sub("", rest, count=1).strip()
        if amount_cents is None or not pix_key:
            return t(self.lang, "transfer_invalid")

        used_today = self.storage.transfers_total_since(self._day_start_utc())
        if used_today + amount_cents > self.transfer_daily_limit_cents:
            return t(self.lang, "transfer_limit",
                     limit=format_money(self.transfer_daily_limit_cents),
                     used=format_money(used_today))

        code = f"{secrets.randbelow(900000) + 100000}"
        self._pending_transfers[sender] = (
            code, amount_cents, pix_key, time.monotonic() + CONFIRM_TTL_SECONDS)
        return t(self.lang, "transfer_confirm",
                 amount=format_money(amount_cents), key=pix_key, code=code)

    def _confirm_transfer(self, sender: str, code: str) -> str:
        pending = self._pending_transfers.get(sender)
        if (pending is None or pending[0] != code
                or time.monotonic() > pending[3]):
            self._pending_transfers.pop(sender, None)  # código errado invalida
            return t(self.lang, "confirm_invalid")
        _, amount_cents, pix_key, _ = self._pending_transfers.pop(sender)
        try:
            ref = self.psp.transfer(amount_cents, pix_key, "PixZap")
        except Exception as exc:  # saldo insuficiente, chave inválida, rede...
            return t(self.lang, "transfer_failed", reason=str(exc))
        self.storage.record_transfer(amount_cents, pix_key, self.psp.name,
                                     ref, sender)
        return t(self.lang, "transfer_done",
                 amount=format_money(amount_cents), key=pix_key, ref=ref)

    def _cancel(self, charge_id: int) -> str:
        charge = self.storage.get_charge(charge_id)
        if charge is None:
            return t(self.lang, "cancel_not_found", id=charge_id)
        if charge.status.value != "pendente":
            return t(self.lang, "cancel_wrong_status", id=charge_id,
                     status=status_label(self.lang, charge.status.value))
        self.storage.mark_canceled(charge_id)
        return t(self.lang, "canceled", summary=charge.summary())

    # ── notificações da conciliação ─────────────────────────────────
    def notify_sellers(self, wa_client, message: str) -> None:
        for number in self.seller_numbers:
            wa_client.send_text(number, message)
